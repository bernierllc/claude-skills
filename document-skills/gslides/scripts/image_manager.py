#!/usr/bin/env python3
"""
Image Manager for Google Slides.

Handles image insertion, positioning, effects, and placeholders.
Phase 4 component for data visualization and business intelligence.
"""

from typing import Dict, Any, Optional, Literal
from dataclasses import dataclass
from pathlib import Path
import logging
import mimetypes

# Set up logging
logger = logging.getLogger(__name__)


@dataclass
class ImagePosition:
    """Position and size for image placement."""
    x: int  # Points from left
    y: int  # Points from top
    width: int  # Points
    height: int  # Points


@dataclass
class CropProperties:
    """Image crop properties."""
    left: float = 0.0  # Left crop ratio (0.0 to 1.0)
    top: float = 0.0  # Top crop ratio (0.0 to 1.0)
    right: float = 0.0  # Right crop ratio (0.0 to 1.0)
    bottom: float = 0.0  # Bottom crop ratio (0.0 to 1.0)


@dataclass
class ImageEffects:
    """Image visual effects."""
    brightness: Optional[float] = None  # -1.0 to 1.0
    contrast: Optional[float] = None  # -1.0 to 1.0
    transparency: Optional[float] = None  # 0.0 (opaque) to 1.0 (transparent)


class ImageManager:
    """
    Manages image insertion and manipulation for Google Slides.

    Provides methods to insert images from URLs or files, replace images,
    crop images, apply effects, and create placeholders.
    """

    # Supported image formats
    SUPPORTED_FORMATS = ['PNG', 'JPEG', 'JPG', 'GIF', 'BMP']

    # EMU conversion constant (1 point = 12700 EMU)
    EMU_PER_POINT = 12700

    def __init__(self, slides_service, drive_service=None):
        """
        Initialize ImageManager.

        Args:
            slides_service: Google Slides API service object
            drive_service: Optional Google Drive API service object
                          (required for uploading local files)
        """
        self.slides_service = slides_service
        self.drive_service = drive_service

    def insert_image(
        self,
        pres_id: str,
        slide_id: str,
        image_url: str,
        position: ImagePosition,
        description: Optional[str] = None
    ) -> str:
        """
        Insert an image from a URL.

        Args:
            pres_id: Presentation ID
            slide_id: Slide object ID
            image_url: Public URL of the image
            position: ImagePosition object for placement
            description: Optional alt text for accessibility

        Returns:
            Image object ID

        Example:
            >>> position = ImagePosition(x=100, y=150, width=300, height=200)
            >>> image_id = manager.insert_image(
            ...     pres_id='1abc...',
            ...     slide_id='slide123',
            ...     image_url='https://example.com/logo.png',
            ...     position=position,
            ...     description='Company logo'
            ... )
        """
        # Generate image ID
        image_id = f'image_{slide_id}_{position.x}_{position.y}'

        # Build create image request
        request = {
            'createImage': {
                'objectId': image_id,
                'url': image_url,
                'elementProperties': {
                    'pageObjectId': slide_id,
                    'size': {
                        'width': {'magnitude': position.width * self.EMU_PER_POINT, 'unit': 'EMU'},
                        'height': {'magnitude': position.height * self.EMU_PER_POINT, 'unit': 'EMU'}
                    },
                    'transform': {
                        'scaleX': 1,
                        'scaleY': 1,
                        'translateX': position.x * self.EMU_PER_POINT,
                        'translateY': position.y * self.EMU_PER_POINT,
                        'unit': 'EMU'
                    }
                }
            }
        }

        # Execute request
        self.slides_service.presentations().batchUpdate(
            presentationId=pres_id,
            body={'requests': [request]}
        ).execute()

        # Add description if provided
        if description:
            self._set_alt_text(pres_id, image_id, description)

        logger.info(f"Inserted image from URL on slide {slide_id}")

        return image_id

    def insert_image_from_file(
        self,
        pres_id: str,
        slide_id: str,
        file_path: str,
        position: ImagePosition,
        description: Optional[str] = None
    ) -> str:
        """
        Insert an image from a local file.

        Uploads file to Google Drive first, then inserts into presentation.

        Args:
            pres_id: Presentation ID
            slide_id: Slide object ID
            file_path: Path to local image file
            position: ImagePosition object for placement
            description: Optional alt text for accessibility

        Returns:
            Image object ID

        Raises:
            ValueError: If drive_service not provided or file not found

        Example:
            >>> position = ImagePosition(x=100, y=150, width=300, height=200)
            >>> image_id = manager.insert_image_from_file(
            ...     pres_id='1abc...',
            ...     slide_id='slide123',
            ...     file_path='/path/to/image.png',
            ...     position=position
            ... )
        """
        if not self.drive_service:
            raise ValueError(
                "drive_service required for uploading local files. "
                "Provide drive_service when initializing ImageManager."
            )

        # Validate file exists
        path = Path(file_path)
        if not path.exists():
            raise FileNotFoundError(f"Image file not found: {file_path}")

        # Validate format
        extension = path.suffix.upper().lstrip('.')
        if extension not in self.SUPPORTED_FORMATS:
            raise ValueError(
                f"Unsupported image format: {extension}. "
                f"Supported: {', '.join(self.SUPPORTED_FORMATS)}"
            )

        # Upload to Drive and get URL
        image_url = self._upload_to_drive(file_path)

        # Insert image
        image_id = self.insert_image(
            pres_id, slide_id, image_url, position, description
        )

        logger.info(f"Inserted image from file {file_path} on slide {slide_id}")

        return image_id

    def replace_image(
        self,
        pres_id: str,
        image_id: str,
        new_image_url: str
    ) -> Dict[str, Any]:
        """
        Replace an existing image with a new one.

        Args:
            pres_id: Presentation ID
            image_id: Existing image object ID
            new_image_url: URL of the new image

        Returns:
            Response from the batchUpdate API call

        Example:
            >>> result = manager.replace_image(
            ...     pres_id='1abc...',
            ...     image_id='image123',
            ...     new_image_url='https://example.com/new-logo.png'
            ... )
        """
        request = {
            'replaceImage': {
                'imageObjectId': image_id,
                'url': new_image_url,
                'imageReplaceMethod': 'CENTER_INSIDE'
            }
        }

        response = self.slides_service.presentations().batchUpdate(
            presentationId=pres_id,
            body={'requests': [request]}
        ).execute()

        logger.info(f"Replaced image {image_id}")

        return response

    def crop_image(
        self,
        pres_id: str,
        image_id: str,
        crop_properties: CropProperties
    ) -> Dict[str, Any]:
        """
        Crop an image.

        Args:
            pres_id: Presentation ID
            image_id: Image object ID
            crop_properties: CropProperties object with crop ratios

        Returns:
            Response from the batchUpdate API call

        Example:
            >>> # Crop 10% from each side
            >>> crop = CropProperties(left=0.1, top=0.1, right=0.1, bottom=0.1)
            >>> result = manager.crop_image(pres_id, 'image123', crop)
        """
        request = {
            'updateImageProperties': {
                'objectId': image_id,
                'imageProperties': {
                    'cropProperties': {
                        'leftOffset': crop_properties.left,
                        'topOffset': crop_properties.top,
                        'rightOffset': crop_properties.right,
                        'bottomOffset': crop_properties.bottom
                    }
                },
                'fields': 'cropProperties'
            }
        }

        response = self.slides_service.presentations().batchUpdate(
            presentationId=pres_id,
            body={'requests': [request]}
        ).execute()

        logger.info(f"Cropped image {image_id}")

        return response

    def apply_image_effects(
        self,
        pres_id: str,
        image_id: str,
        effects: ImageEffects
    ) -> Dict[str, Any]:
        """
        Apply visual effects to an image.

        Args:
            pres_id: Presentation ID
            image_id: Image object ID
            effects: ImageEffects object with effect values

        Returns:
            Response from the batchUpdate API call

        Example:
            >>> # Increase brightness, add transparency
            >>> effects = ImageEffects(brightness=0.3, transparency=0.2)
            >>> result = manager.apply_image_effects(pres_id, 'image123', effects)
        """
        requests = []

        # Brightness
        if effects.brightness is not None:
            requests.append({
                'updateImageProperties': {
                    'objectId': image_id,
                    'imageProperties': {
                        'brightness': effects.brightness
                    },
                    'fields': 'brightness'
                }
            })

        # Contrast
        if effects.contrast is not None:
            requests.append({
                'updateImageProperties': {
                    'objectId': image_id,
                    'imageProperties': {
                        'contrast': effects.contrast
                    },
                    'fields': 'contrast'
                }
            })

        # Transparency
        if effects.transparency is not None:
            requests.append({
                'updateImageProperties': {
                    'objectId': image_id,
                    'imageProperties': {
                        'transparency': effects.transparency
                    },
                    'fields': 'transparency'
                }
            })

        # Execute requests
        if requests:
            response = self.slides_service.presentations().batchUpdate(
                presentationId=pres_id,
                body={'requests': requests}
            ).execute()

            logger.info(f"Applied effects to image {image_id}")

            return response

        return {'no_effects_applied': True}

    def create_image_placeholder(
        self,
        pres_id: str,
        slide_id: str,
        position: ImagePosition,
        placeholder_color: str = '#e5e7eb',
        text: Optional[str] = None
    ) -> str:
        """
        Create an image placeholder (colored rectangle).

        Useful for templates or when image is not yet available.

        Args:
            pres_id: Presentation ID
            slide_id: Slide object ID
            position: ImagePosition object for placement
            placeholder_color: Hex color for placeholder background
            text: Optional text to display in placeholder

        Returns:
            Placeholder shape object ID

        Example:
            >>> position = ImagePosition(x=100, y=150, width=300, height=200)
            >>> placeholder_id = manager.create_image_placeholder(
            ...     pres_id='1abc...',
            ...     slide_id='slide123',
            ...     position=position,
            ...     text='Image placeholder'
            ... )
        """
        # Generate placeholder ID
        placeholder_id = f'placeholder_{slide_id}_{position.x}_{position.y}'

        # Create rectangle shape
        request = {
            'createShape': {
                'objectId': placeholder_id,
                'shapeType': 'RECTANGLE',
                'elementProperties': {
                    'pageObjectId': slide_id,
                    'size': {
                        'width': {'magnitude': position.width * self.EMU_PER_POINT, 'unit': 'EMU'},
                        'height': {'magnitude': position.height * self.EMU_PER_POINT, 'unit': 'EMU'}
                    },
                    'transform': {
                        'scaleX': 1,
                        'scaleY': 1,
                        'translateX': position.x * self.EMU_PER_POINT,
                        'translateY': position.y * self.EMU_PER_POINT,
                        'unit': 'EMU'
                    }
                }
            }
        }

        self.slides_service.presentations().batchUpdate(
            presentationId=pres_id,
            body={'requests': [request]}
        ).execute()

        # Style placeholder
        rgb = self._hex_to_rgb(placeholder_color)

        style_request = {
            'updateShapeProperties': {
                'objectId': placeholder_id,
                'shapeProperties': {
                    'shapeBackgroundFill': {
                        'solidFill': {
                            'color': {'rgbColor': rgb}
                        }
                    }
                },
                'fields': 'shapeBackgroundFill.solidFill.color'
            }
        }

        self.slides_service.presentations().batchUpdate(
            presentationId=pres_id,
            body={'requests': [style_request]}
        ).execute()

        # Add text if provided
        if text:
            text_request = {
                'insertText': {
                    'objectId': placeholder_id,
                    'text': text,
                    'insertionIndex': 0
                }
            }

            self.slides_service.presentations().batchUpdate(
                presentationId=pres_id,
                body={'requests': [text_request]}
            ).execute()

        logger.info(f"Created image placeholder on slide {slide_id}")

        return placeholder_id

    def _upload_to_drive(self, file_path: str) -> str:
        """
        Upload a local file to Google Drive and return public URL.

        Args:
            file_path: Path to local file

        Returns:
            Public URL for the uploaded file
        """
        from googleapiclient.http import MediaFileUpload

        path = Path(file_path)

        # Determine MIME type
        mime_type, _ = mimetypes.guess_type(file_path)
        if not mime_type or not mime_type.startswith('image/'):
            mime_type = 'image/png'  # Default

        # Upload file
        file_metadata = {
            'name': path.name,
            'mimeType': mime_type
        }

        media = MediaFileUpload(
            file_path,
            mimetype=mime_type,
            resumable=True
        )

        file = self.drive_service.files().create(
            body=file_metadata,
            media_body=media,
            fields='id'
        ).execute()

        drive_file_id = file.get('id')

        # Make file publicly readable
        permission = {
            'type': 'anyone',
            'role': 'reader'
        }

        self.drive_service.permissions().create(
            fileId=drive_file_id,
            body=permission
        ).execute()

        # Return download URL
        return f"https://drive.google.com/uc?export=download&id={drive_file_id}"

    def _set_alt_text(
        self,
        pres_id: str,
        image_id: str,
        description: str
    ):
        """
        Set image alt text for accessibility.

        Args:
            pres_id: Presentation ID
            image_id: Image object ID
            description: Alt text description
        """
        request = {
            'updatePageElementAltText': {
                'objectId': image_id,
                'title': 'Image',
                'description': description
            }
        }

        self.slides_service.presentations().batchUpdate(
            presentationId=pres_id,
            body={'requests': [request]}
        ).execute()

    @staticmethod
    def _hex_to_rgb(hex_color: str) -> Dict[str, float]:
        """
        Convert hex color to RGB values (0.0 to 1.0).

        Args:
            hex_color: Hex color string (e.g., '#FF5733' or 'FF5733')

        Returns:
            Dictionary with 'red', 'green', 'blue' keys (values 0.0-1.0)
        """
        # Remove '#' if present
        hex_color = hex_color.lstrip('#')

        # Convert to RGB (0-255)
        r = int(hex_color[0:2], 16)
        g = int(hex_color[2:4], 16)
        b = int(hex_color[4:6], 16)

        # Convert to 0.0-1.0 range
        return {
            'red': r / 255.0,
            'green': g / 255.0,
            'blue': b / 255.0
        }
