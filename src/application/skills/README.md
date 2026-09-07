# Skills System Documentation Note

This system follows Anthropic Claude Code Skills / LangChain Tool Schema best practices:

1. **Progressive Disclosure**: L1 (TOOLS.md) → L2 (SKILL.md) → L3 (references/scripts)
2. **YAML Frontmatter**: Parsed with yaml.safe_load
3. **Hub-and-Spoke**: SKILL.md is routing, references/ holds detailed specs
4. **Code-First**: scripts/ for deterministic tasks
5. **Trigger Words**: when_to_use / when_not_to_use / triggers for LLM-based routing
6. **Composability**: depends_on for skill chains
