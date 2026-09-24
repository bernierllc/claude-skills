from datetime import datetime
from scripts.updates_structures import (
    UpdatesLocation, UpdatesPattern, FormatTemplate,
    ComponentStyle, UpdateInfo
)

def test_updates_location_tab():
    """Test UpdatesLocation for tab-based location."""
    loc = UpdatesLocation(
        location_type='tab',
        tab_id='t.123',
        header_index=None,
        header_text='Updates'
    )
    assert loc.location_type == 'tab'
    assert loc.tab_id == 't.123'
    assert loc.is_tab()


def test_updates_location_header():
    """Test UpdatesLocation for header-based location."""
    loc = UpdatesLocation(
        location_type='header',
        tab_id=None,
        header_index=450,
        header_text='Document Update Log'
    )
    assert loc.location_type == 'header'
    assert loc.header_index == 450
    assert not loc.is_tab()


def test_updates_pattern():
    """Test UpdatesPattern with format template."""
    template = FormatTemplate(
        date_format='**MMMM DD, YYYY**',
        date_style={'bold': True, 'italic': False},
        bullet_style='-',
        entry_components=[]
    )
    pattern = UpdatesPattern(prepend=True, format_template=template)
    assert pattern.prepend is True
    assert pattern.format_template.bullet_style == '-'


def test_update_info():
    """Test UpdateInfo dataclass."""
    info = UpdateInfo(
        date=datetime(2025, 10, 31),
        summary='Added market analysis insights',
        sections_modified=['Market Analysis', 'Competitive Landscape'],
        source_attribution='Customer feedback meeting on 10/31/25'
    )
    assert len(info.sections_modified) == 2
    assert 'Market Analysis' in info.sections_modified
