# Notebook System - Markdown Parser

## Overview

**MarkdownParser** parses markdown files with embedded exhibit definitions using `$exhibit${...}` and `$filter${...}` syntax.

## Syntax

### Exhibit Syntax

```markdown
$exhibit${
  "type": "line_chart",
  "title": "Stock Prices",
  "query": {
    "model": "company",
    "table": "fact_prices",
    "measures": ["close"]
  },
  "x_axis": "date",
  "y_axis": "close"
}
```

### Filter Syntax

```markdown
$filter${
  "type": "dimension_selector",
  "dimension": "ticker",
  "model": "company",
  "label": "Select Tickers"
}
```

## Parser Implementation

```python
# File: app/notebook/parsers/markdown_parser.py:20-150

class MarkdownNotebookParser:
    """Parser for markdown notebooks with exhibits."""

    EXHIBIT_PATTERN = r'\$exhibit\$\{([^}]+)\}'
    FILTER_PATTERN = r'\$filter\$\{([^}]+)\}'

    def __init__(self, repo_root: Path):
        self.repo_root = repo_root

    def parse_file(self, path: str) -> NotebookConfig:
        """
        Parse markdown file.

        Args:
            path: Path to .md file

        Returns:
            NotebookConfig with exhibits and filters
        """
        with open(path, 'r') as f:
            content = f.read()
        
        return self.parse_content(content)

    def parse_content(self, content: str) -> NotebookConfig:
        """
        Parse markdown content.

        Steps:
        1. Extract exhibits using regex
        2. Extract filters using regex
        3. Parse JSON configs
        4. Build NotebookConfig
        """
        # Extract exhibits
        exhibits = []
        for match in re.finditer(self.EXHIBIT_PATTERN, content, re.DOTALL):
            json_str = match.group(1)
            try:
                config = json.loads(json_str)
                exhibit = self._create_exhibit(config)
                exhibits.append(exhibit)
            except json.JSONDecodeError as e:
                raise ValueError(f"Invalid exhibit JSON: {e}")
        
        # Extract filters
        filters = []
        for match in re.finditer(self.FILTER_PATTERN, content, re.DOTALL):
            json_str = match.group(1)
            try:
                config = json.loads(json_str)
                filter_def = self._create_filter(config)
                filters.append(filter_def)
            except json.JSONDecodeError as e:
                raise ValueError(f"Invalid filter JSON: {e}")
        
        # Build notebook config
        return NotebookConfig(
            title=self._extract_title(content),
            exhibits=exhibits,
            filters=filters,
            content=content
        )

    def _create_exhibit(self, config: Dict) -> Exhibit:
        """Create Exhibit from config dict."""
        exhibit_type = config.get('type', 'unknown')
        
        return Exhibit(
            type=ExhibitType(exhibit_type),
            title=config.get('title', ''),
            query=config.get('query', {}),
            config=config
        )

    def _create_filter(self, config: Dict) -> FilterDefinition:
        """Create FilterDefinition from config dict."""
        return FilterDefinition(
            type=config.get('type'),
            dimension=config.get('dimension'),
            model=config.get('model'),
            label=config.get('label'),
            config=config
        )

    def _extract_title(self, content: str) -> str:
        """Extract title from first H1."""
        match = re.search(r'^#\s+(.+)$', content, re.MULTILINE)
        return match.group(1) if match else "Untitled"
```

## Example Notebook

```markdown
# Stock Performance Analysis

This notebook analyzes stock performance over time.

## Filters

Select tickers to analyze:

$filter${
  "type": "dimension_selector",
  "dimension": "ticker",
  "model": "company",
  "label": "Select Tickers",
  "multi_select": true
}

Select date range:

$filter${
  "type": "date_range",
  "dimension": "date",
  "label": "Date Range"
}

## Price Trends

$exhibit${
  "type": "line_chart",
  "title": "Closing Prices",
  "query": {
    "model": "company",
    "table": "fact_prices",
    "measures": ["close"]
  },
  "x_axis": "date",
  "y_axis": "close",
  "group_by": "ticker"
}

## Volume Analysis

$exhibit${
  "type": "bar_chart",
  "title": "Trading Volume",
  "query": {
    "model": "company",
    "table": "fact_prices",
    "measures": ["volume"],
    "aggregation": "sum(volume)",
    "group_by": ["ticker"]
  },
  "x_axis": "ticker",
  "y_axis": "volume"
}

## Summary Metrics

$exhibit${
  "type": "metric_cards",
  "metrics": [
    {
      "name": "Avg Close",
      "query": {
        "model": "company",
        "table": "fact_prices",
        "aggregation": "avg(close)"
      },
      "format": "currency"
    },
    {
      "name": "Total Volume",
      "query": {
        "model": "company",
        "table": "fact_prices",
        "aggregation": "sum(volume)"
      },
      "format": "number"
    }
  ]
}
```

**File**: `/home/user/de_Funk/docs/guide/3-architecture/components/notebook-system/markdown-parser.md`
