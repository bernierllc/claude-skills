# Contributing to Bernier LLC Skills

Thank you for your interest in contributing to our skills repository! This document provides guidelines for contributing new skills or improvements to existing ones.

## Getting Started

### Prerequisites

- Familiarity with Claude and how skills work
- Understanding of the specific domain your skill addresses
- Basic knowledge of Markdown and YAML frontmatter

### Repository Structure

```
/
├── document-skills/     # Document creation and editing skills
├── example-skills/      # Other example skills (art, design, dev, etc.)
├── LICENSE             # Apache 2.0 license
└── README.md           # Main repository documentation
```

## How to Contribute

### 1. Fork the Repository

Fork `bernierllc/skills` to your own GitHub account.

### 2. Create a Branch

```bash
git checkout -b feature/your-skill-name
```

### 3. Add Your Skill

Create a new directory for your skill with at minimum a `SKILL.md` file:

```
your-skill-name/
├── SKILL.md           # Required: Main skill instructions
├── README.md          # Optional but recommended: Usage documentation
├── examples/          # Optional: Example scripts or usage
└── scripts/           # Optional: Supporting code/scripts
```

### 4. Write Your SKILL.md

Every skill must have a `SKILL.md` file with proper YAML frontmatter:

```markdown
---
name: your-skill-name
description: "Clear, complete description of what this skill does and when to use it"
---

# Your Skill Name

[Detailed instructions for Claude to follow]

## When to Use This Skill

[Clear guidance on when this skill should be activated]

## Core Workflow

[Step-by-step instructions]

## Examples

[Concrete examples of usage]
```

### 5. Test Your Skill

Before submitting:

- Test the skill in Claude Code or Claude.ai
- Verify all instructions are clear and work as intended
- Check that examples are accurate and helpful
- Ensure documentation is complete

### 6. Submit a Pull Request

1. Commit your changes with clear, descriptive messages
2. Push to your fork
3. Create a Pull Request to `bernierllc/skills`
4. Describe what your skill does and why it's useful

## Skill Guidelines

### Quality Standards

**Clear Instructions**
- Write instructions as if explaining to someone unfamiliar with the domain
- Use specific, actionable language
- Avoid ambiguity

**Good Examples**
- Provide concrete examples of inputs and expected outputs
- Show edge cases and how to handle them
- Include both simple and complex scenarios

**Documentation**
- Include a README.md explaining setup and usage
- Document any dependencies or requirements
- Provide troubleshooting guidance

### Skill Design Principles

1. **Single Responsibility**: Each skill should focus on one well-defined task
2. **Composability**: Skills should work well with other skills
3. **Maintainability**: Write clear, well-organized instructions
4. **Robustness**: Handle edge cases and provide clear error guidance

### What Makes a Good Skill

✅ **Good:**
- Solves a specific, well-defined problem
- Has clear activation criteria
- Includes comprehensive examples
- Documents dependencies
- Provides troubleshooting guidance

❌ **Avoid:**
- Overly broad, vague instructions
- Unclear when the skill should activate
- Missing examples or documentation
- Undocumented dependencies
- No error handling guidance

## Code of Conduct

### Our Standards

- Be respectful and inclusive
- Provide constructive feedback
- Focus on what is best for the community
- Show empathy towards other contributors

### Unacceptable Behavior

- Harassment or discriminatory language
- Personal attacks or trolling
- Publishing others' private information
- Other conduct that could be considered inappropriate

## Licensing

By contributing to this repository, you agree that your contributions will be licensed under the Apache License 2.0.

## Questions?

If you have questions about contributing, feel free to:
- Open an issue for discussion
- Review existing skills for examples
- Check the main README for more information

## Recognition

Contributors will be recognized in commit messages and pull request acknowledgments. Significant contributions may be highlighted in release notes.

Thank you for helping improve Claude skills!

---

**Bernier LLC**
Skills Repository Maintainers
