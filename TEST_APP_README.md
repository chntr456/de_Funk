# de_Funk Test Application Script

Comprehensive testing script to validate the reorganized project structure.

## Features

✅ **Directory Structure Validation** - Verifies all expected directories exist
✅ **Import Testing** - Tests imports from all packages (core, models, datapipelines, app, orchestration)
✅ **Functional Testing** - Tests DuckDB connection, RepoContext, ModelRegistry, NotebookParser, etc.
✅ **UI Component Testing** - Validates all Streamlit UI components
✅ **Color-Coded Output** - Easy-to-read results with ✓/✗ indicators
✅ **Detailed Error Messages** - Shows exactly what failed and why

## Usage

### Quick Test (Imports Only)
```bash
python test_app.py --quick
```
Tests directory structure and all import statements (~5 seconds)

### Full Test (With Functional Tests)
```bash
python test_app.py
```
Tests everything including actual initialization and functionality (~10 seconds)

### Verbose Mode
```bash
python test_app.py --verbose
```
Shows detailed logging of each test step

### Combined
```bash
python test_app.py --quick --verbose
```

## Test Categories

### 1. Directory Structure
Validates all expected directories exist:
- core/
- models/ (with all subdirectories)
- datapipelines/ (with all subdirectories)
- orchestration/
- app/

### 2. Core Package Tests
Tests imports from `core/`:
- `core.connection` - DataConnection base class
- `core.duckdb_connection` - DuckDB connection
- `core.context` - RepoContext
- `core.validation` - Validation utilities

### 3. Models Package Tests
Tests imports from `models/`:
- `models.registry` - ModelRegistry
- `models.loaders.parquet_loader` - Parquet data loader
- `models.loaders.parquet_loader_optimized` - Optimized loader
- `models.builders.company_silver_builder` - Silver layer builder
- `models.api.session` - Model API session

### 4. Data Pipelines Tests
Tests imports from `datapipelines/`:
- `datapipelines.ingestors.base_ingestor` - Base ingestor
- `datapipelines.facets.base_facet` - Base facet
- `datapipelines.base.http_client` - HTTP client

### 5. App Package Tests
Tests imports from `app/`:
- `app.notebook.schema` - Notebook schema
- `app.notebook.parser` - Notebook parser
- `app.notebook.api.notebook_session` - Notebook session
- `app.services.storage_service` - Storage service
- `app.ui.components.*` - All UI components

### 6. Orchestration Tests
Tests imports from `orchestration/`:
- `orchestration.common.path_utils` - Path utilities
- `orchestration.orchestrator` - Main orchestrator

### 7. Functional Tests (Full Mode Only)

**DuckDB Connection**
- Initializes in-memory DuckDB database
- Executes basic queries
- Verifies connection cleanup

**RepoContext**
- Initializes with DuckDB connection
- Validates configuration loading
- Tests connection creation

**ModelRegistry**
- Loads model configurations from configs/models/
- Lists available models
- Validates model schemas

**NotebookParser**
- Parses YAML notebook configurations
- Validates notebook structure
- Tests exhibit and filter definitions

**StorageService**
- Initializes with DuckDB + ModelRegistry
- Lists available models
- Tests table loading

**UI Components**
- Tests all exhibit renderers (line charts, bar charts, metrics, tables)
- Validates theme system

## Output Example

```
======================================================================
de_Funk Application Test Suite
======================================================================

Testing directory structure...

Testing core/ imports...

Testing models/ imports...

Testing datapipelines/ imports...

Testing app/ imports...

Testing orchestration/ imports...

======================================================================
TEST SUMMARY
======================================================================
✓ Directory Structure............................... PASS
✓ Import core.connection............................ PASS
✓ Import core.duckdb_connection..................... PASS
✓ Import core.context............................... PASS
✓ Import models.registry............................ PASS
...

======================================================================
Total: 21 | Passed: 18 | Failed: 3 | Warnings: 0
======================================================================
```

## Exit Codes

- `0` - All tests passed ✅
- `1` - Some tests failed ❌

## Troubleshooting

### ImportError: No module named 'X'
**Cause**: Missing `__init__.py` file or incorrect import path
**Fix**: Check that directory has `__init__.py` and imports use correct package names

### Failed tests after reorganization
**Cause**: Some files may still have old `src.*` import paths
**Fix**: Run `python update_imports.py` to fix all imports

### DuckDB connection fails
**Cause**: DuckDB not installed
**Fix**: `pip install duckdb`

### Model/Notebook not found warnings
**Cause**: Missing configuration files
**Fix**: Ensure configs/models/ and configs/notebooks/ contain YAML files

## Integration with CI/CD

Add to your CI pipeline:
```yaml
- name: Run Application Tests
  run: python test_app.py
```

Or in GitHub Actions:
```yaml
- name: Test Application Structure
  run: |
    python test_app.py
    if [ $? -ne 0 ]; then
      echo "❌ Tests failed!"
      exit 1
    fi
```

## Development Workflow

After making changes to the project structure:

1. **Run quick test** to verify imports:
   ```bash
   python test_app.py --quick
   ```

2. **Run full test** before committing:
   ```bash
   python test_app.py
   ```

3. **Fix any failures**, then commit:
   ```bash
   git add -A
   git commit -m "Fix: [description]"
   ```

## What's Tested vs Not Tested

### ✅ Tested
- Directory structure
- Import paths
- Module initialization
- Basic functionality (DuckDB, parsing, etc.)
- Configuration loading

### ❌ Not Tested
- Business logic correctness
- Data transformation accuracy
- UI rendering (requires Streamlit session)
- API endpoints
- Database query results

For comprehensive testing, use:
- Unit tests in `tests/`
- Integration tests with real data
- End-to-end UI testing with Streamlit

## See Also

- `migrate_structure.py` - Migration script
- `update_imports.py` - Import update script
- `docs/STORAGE_REDESIGN.md` - Architecture documentation
