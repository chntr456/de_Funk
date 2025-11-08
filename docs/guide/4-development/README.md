# Development & Roadmap

> **Track progress, plan improvements, and coordinate development efforts**

This section contains todos, roadmap planning, and backlog items for ongoing platform development.

---

## 📚 What's in This Section

### **[Todo Tracker](todo-tracker.md)**
Master todo tracker for platform improvements organized by priority and category.

**Categories:**
- Critical bugs and fixes
- Performance optimizations
- Feature enhancements
- Documentation improvements
- Testing and validation
- Technical debt

---

### **[Roadmap](roadmap.md)**
Future features and strategic initiatives planned for de_Funk.

**Topics:**
- Short-term goals (next 3 months)
- Medium-term initiatives (3-6 months)
- Long-term vision (6-12 months)
- Community requests and feedback

---

### **[Backlog](backlog/)**
Organized backlog items by section:

- **[Getting Started Todos](backlog/getting-started-todos.md)** - Documentation and onboarding improvements
- **[Models Todos](backlog/models-todos.md)** - New models and model enhancements
- **[Architecture Todos](backlog/architecture-todos.md)** - Architecture refactoring and improvements

---

## 🎯 Current Development Focus

### **Q4 2024 Priorities**

1. **Documentation Consolidation** ✅ (In Progress)
   - Consolidate 50+ scattered docs into unified guide
   - Create comprehensive getting started guides
   - Document all implemented models
   - Create architecture component docs

2. **Performance Optimization**
   - DuckDB query optimization
   - Partition pruning improvements
   - Lazy loading enhancements

3. **Testing Coverage**
   - Unit tests for core components
   - Integration tests for pipelines
   - End-to-end UI tests

4. **New Data Sources**
   - Additional API providers
   - Data source connectors
   - Real-time data streams

---

## 📊 Development Metrics

### **Code Base Statistics**
- **Lines of Code:** ~15,000 Python
- **Models:** 5 implemented
- **Data Sources:** 3 (Polygon, BLS, Chicago)
- **Components:** 6 major subsystems
- **Configuration Files:** 50+ YAML/JSON

### **Test Coverage**
- **Unit Tests:** 40% coverage (target: 80%)
- **Integration Tests:** 20% coverage (target: 60%)
- **E2E Tests:** 10% coverage (target: 40%)

### **Documentation Coverage**
- **Component Docs:** 100% ✅
- **Model Docs:** 100% ✅
- **How-To Guides:** 60% (7 of 12 planned)
- **API Docs:** 40% (needs improvement)

---

## 🚀 Contribution Workflow

### **1. Pick a Todo**
Browse [Todo Tracker](todo-tracker.md) for available tasks organized by priority.

### **2. Create a Branch**
```bash
git checkout -b feature/your-feature-name
```

### **3. Make Changes**
- Write code following project conventions
- Add tests for new functionality
- Update documentation

### **4. Test Locally**
```bash
# Run tests
pytest tests/

# Run type checking
mypy .

# Run linting
flake8 .
```

### **5. Submit PR**
- Describe changes and motivation
- Reference related todos/issues
- Ensure CI passes

---

## 📝 Development Guidelines

### **Code Style**
- **PEP 8** for Python code
- **Type hints** for all public APIs
- **Docstrings** for all classes and functions
- **Comments** for complex logic

### **Testing**
- **Unit tests** for individual components
- **Integration tests** for component interactions
- **E2E tests** for critical user workflows
- **>80% coverage** for new code

### **Documentation**
- Update guide docs for new features
- Add code examples to how-to guides
- Document design decisions
- Keep YAML schemas up to date

### **Commit Messages**
```
<type>(<scope>): <subject>

<body>

<footer>
```

**Types:** feat, fix, docs, style, refactor, test, chore

**Example:**
```
feat(models): Add real-time stock data model

- Add streaming facet for websocket connections
- Implement real-time price aggregation
- Add streaming exhibit for live charts

Closes #123
```

---

## 🔧 Development Setup

### **Local Environment**
```bash
# Clone repository
git clone https://github.com/your-org/de_Funk.git
cd de_Funk

# Create virtual environment
python -m venv venv
source venv/bin/activate  # or venv\Scripts\activate on Windows

# Install dependencies
pip install -r requirements.txt
pip install -r requirements-dev.txt  # Development tools

# Install pre-commit hooks
pre-commit install
```

### **Development Tools**
- **pytest** - Testing framework
- **mypy** - Type checking
- **flake8** - Linting
- **black** - Code formatting
- **pre-commit** - Git hooks

### **IDE Setup**
Recommended: VS Code with extensions:
- Python
- Pylance
- Python Test Explorer
- YAML

---

## 🎓 Architecture Decisions

Major architectural decisions are documented in the [Architecture](../3-architecture/) section.

**Recent Decisions:**
1. **DuckDB as Default** - 10-100x faster than Spark for analytics
2. **YAML-Driven Models** - Declarative configuration over code
3. **Markdown Notebooks** - Lightweight, version-controllable analytics
4. **Medallion Architecture** - Bronze (raw) → Silver (curated) layers

---

## 📋 Issue Labels

GitHub issue labels for organization:

| Label | Purpose |
|-------|---------|
| `bug` | Something isn't working |
| `enhancement` | New feature or request |
| `documentation` | Documentation improvements |
| `performance` | Performance optimization |
| `testing` | Test coverage improvements |
| `good first issue` | Good for newcomers |
| `help wanted` | Community help requested |
| `high priority` | Critical issues |
| `technical debt` | Code quality improvements |

---

## 🚀 Release Process

### **Version Scheme**
Semantic versioning: `MAJOR.MINOR.PATCH`

**Example:** `1.2.3`
- **MAJOR:** Breaking changes
- **MINOR:** New features (backward compatible)
- **PATCH:** Bug fixes

### **Release Checklist**
- [ ] All tests pass
- [ ] Documentation updated
- [ ] CHANGELOG updated
- [ ] Version bumped
- [ ] Tag created
- [ ] Release notes written

---

## 🔍 Finding Work

### **For Beginners**
Start with `good first issue` label:
- Documentation improvements
- Small bug fixes
- Test additions

### **For Experienced Developers**
Check `high priority` and `enhancement` labels:
- New features
- Performance optimizations
- Architecture improvements

### **For Domain Experts**
Focus on area of expertise:
- Data engineers → Data pipeline improvements
- ML engineers → Forecast model enhancements
- Frontend developers → UI/UX improvements
- DevOps → Deployment and scaling

---

## 📞 Getting Help

**Questions?**
- Check [Getting Started](../1-getting-started/) docs
- Read relevant [Architecture](../3-architecture/) docs
- Ask in project discussions

**Found a bug?**
- Check [Todo Tracker](todo-tracker.md)
- Create GitHub issue with details
- Include reproducible example

**Want to contribute?**
- Read contribution guidelines above
- Pick an item from [Todo Tracker](todo-tracker.md)
- Submit a PR

---

## 🎯 Next Steps

**Ready to contribute?** Check out the **[Todo Tracker](todo-tracker.md)**

**Planning new features?** Review the **[Roadmap](roadmap.md)**

**Working on specific area?** See **[Backlog](backlog/)** for categorized todos

---

**Last Updated:** 2024-11-08
**Active Contributors:** Check GitHub contributors
**Open Todos:** See [Todo Tracker](todo-tracker.md)
