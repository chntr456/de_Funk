# Graph Architecture Refactor - Implementation Plan

Based on the code scan in GRAPH_REFACTOR_SCAN.md

---

## Phase 1: Remove Graph Deployment from BaseModel.build()

### Files to Modify:
1. **models/base/model.py**

### Changes:

#### Before:
```python
def build(self) -> Tuple[Dict[str, DataFrame], Dict[str, DataFrame]]:
    self.before_build()
    
    nodes = self._build_nodes()
    self._apply_edges(nodes)           # REMOVE
    paths = self._materialize_paths(nodes)  # REMOVE
    
    dims = {k: v for k, v in nodes.items() if k.startswith("dim_")}
    facts = {
        **{k: v for k, v in nodes.items() if k.startswith("fact_")},
        **paths  # REMOVE
    }
    
    dims, facts = self.after_build(dims, facts)
    return dims, facts
```

#### After:
```python
def build(self) -> Tuple[Dict[str, DataFrame], Dict[str, DataFrame]]:
    """
    Build model tables from Bronze layer.
    
    Simplified to just build individual tables - all graph operations
    (joins, relationships, etc.) are handled at query time by GraphQueryPlanner.
    """
    self.before_build()
    
    # Build all tables from Bronze
    nodes = self._build_nodes()
    
    # Separate into dimensions and facts by naming convention
    dims = {k: v for k, v in nodes.items() if k.startswith("dim_")}
    facts = {k: v for k, v in nodes.items() if k.startswith("fact_")}
    
    # Allow model-specific customization
    dims, facts = self.after_build(dims, facts)
    
    return dims, facts
```

#### Methods to Remove:
```python
def _apply_edges(self, nodes: Dict[str, DataFrame]) -> None:
    # DELETE ENTIRE METHOD (lines 462-513)
    
def _materialize_paths(self, nodes: Dict[str, DataFrame]) -> Dict[str, DataFrame]:
    # DELETE ENTIRE METHOD (lines 515-584)
    
def _find_edge(self, from_id: str, to_id: str) -> Optional[Dict]:
    # DELETE ENTIRE METHOD (lines 586-595)
```

**Note:** Keep `_build_nodes()` - it's still needed to load tables from Bronze

---

## Phase 2: Add UniversalSession Graph Methods

### Files to Modify:
1. **models/api/session.py**

### New Methods to Add:

```python
def should_apply_cross_model_filter(
    self, 
    source_model: str, 
    target_model: str
) -> bool:
    """
    Check if a filter from source_model should be applied to target_model.
    
    Returns True if:
    - Same model (always apply)
    - Models are related via graph (cross-model filter is valid)
    
    Args:
        source_model: Model that defines the filter
        target_model: Model being queried
        
    Returns:
        True if filter should be applied
        
    Example:
        # Apply equity filters to equity model
        session.should_apply_cross_model_filter('equity', 'equity')  # True
        
        # Apply equity filters to forecast model (related via graph)
        session.should_apply_cross_model_filter('equity', 'forecast')  # True
        
        # Don't apply equity filters to unrelated city_finance
        session.should_apply_cross_model_filter('equity', 'city_finance')  # False
    """
    # Same model - always apply
    if source_model == target_model:
        return True
    
    # Check if models are related via graph
    if hasattr(self, 'model_graph'):
        return self.model_graph.are_related(target_model, source_model)
    
    # No graph available - be conservative, don't apply
    return False


def get_model_edge_metadata(
    self,
    from_table: str,  # Can be "model.table" or just "table"
    to_table: str     # Can be "model.table" or just "table"  
) -> Optional[Dict[str, Any]]:
    """
    Get edge metadata between two tables (intra-model or cross-model).
    
    Replaces direct YAML config access in get_filter_column_mappings.
    
    Args:
        from_table: Source table (e.g., "fact_equity_prices" or "equity.fact_equity_prices")
        to_table: Target table (e.g., "core.dim_calendar")
        
    Returns:
        Edge metadata dict with 'on', 'type', 'description', or None
    """
    # Parse model.table format
    from_model, from_tbl = self._parse_table_ref(from_table)
    to_model, to_tbl = self._parse_table_ref(to_table)
    
    # Get source model config
    model_config = self.registry.get_model_config(from_model)
    graph_config = model_config.get('graph', {})
    
    # Find matching edge
    for edge in graph_config.get('edges', []):
        if edge.get('from') == from_tbl and to_tbl in edge.get('to', ''):
            return edge
            
    return None


def _parse_table_ref(self, table_ref: str) -> Tuple[str, str]:
    """
    Parse table reference into (model_name, table_name).
    
    Args:
        table_ref: Either "table" or "model.table"
        
    Returns:
        Tuple of (model_name, table_name)
    """
    if '.' in table_ref:
        parts = table_ref.split('.', 1)
        return parts[0], parts[1]
    else:
        # No model specified - caller must provide context
        raise ValueError(f"Table ref '{table_ref}' missing model prefix")
```

### Methods to Refactor:

#### get_filter_column_mappings (lines 338-417)

**Before:**
```python
# Read YAML directly
model_config = self.registry.get_model_config(model_name)
for edge in model_config['graph']['edges']:
    # Process...
```

**After:**
```python
# Use ModelGraph helper
edge = self.get_model_edge_metadata(
    f"{model_name}.{table_name}",
    "core.dim_calendar"
)
if edge:
    # Process edge['on'] conditions
```

---

## Phase 3: Update NotebookManager

### Files to Modify:
1. **app/notebook/managers/notebook_manager.py**

### Changes:

#### Remove Method:
```python
def _models_are_related(self, model_a: str, model_b: str) -> bool:
    # DELETE ENTIRE METHOD (lines 664-675)
    # Logic moved to session.should_apply_cross_model_filter()
```

#### Update _build_filters (around line 580):

**Before:**
```python
elif not self._models_are_related(exhibit_model, filter_model):
    # No relationship declared - skip this filter
    continue
```

**After:**
```python
elif not self.session.should_apply_cross_model_filter(filter_model, exhibit_model):
    # No relationship declared - skip this filter
    continue
```

---

## Phase 4: Document Changes

### Files to Create/Update:

1. **GRAPH_REFACTOR_CHANGELOG.md** - Detailed changelog
2. **docs/GRAPH_ARCHITECTURE.md** - Update architecture docs
3. **CLAUDE.md** - Update project guide

---

## Testing Plan

### Unit Tests:
1. Test BaseModel.build() still works
2. Test session.should_apply_cross_model_filter()
3. Test session.get_model_edge_metadata()

### Integration Tests:
1. Run build_all_models.py
2. Test cross-model filters in notebooks
3. Test UI model graph viewer
4. Verify examples still work

### Smoke Tests:
```bash
# Build equity model
python -m scripts.rebuild_model --model equity

# Run app
python run_app.py

# Check graph visualization works
# Check cross-model filtering works
```

---

## Rollback Plan

If issues arise:
1. Revert models/base/model.py to restore _apply_edges/_materialize_paths
2. Revert models/api/session.py changes
3. Revert app/notebook/managers/notebook_manager.py changes

All changes are isolated - no database schema changes, no YAML config changes.

---

## Success Criteria

- ✅ BaseModel.build() is simpler (< 20 lines)
- ✅ No direct YAML graph access outside ModelGraph
- ✅ All graph logic centralized in UniversalSession
- ✅ All existing tests pass
- ✅ UI graph viewer still works
- ✅ Cross-model filtering still works
- ✅ Build scripts still work
- ✅ Examples still run

