# Documentation Migration Guide

**Date:** 2024-11-08

The de_Funk documentation has been consolidated from 50+ scattered files into a unified, comprehensive guide.

---

## 📍 Where to Find Documentation Now

### **Main Documentation**
All current documentation is now in **[docs/guide/](guide/README.md)**

### **Old Documentation**
Legacy docs have been archived in **[docs/archive/](archive/README.md)**

---

## 🗺️ Documentation Map

### **Quick Start & Tutorials**
| Old Location | New Location |
|--------------|--------------|
| `QUICKSTART.md` | [docs/guide/1-getting-started/quickstart.md](guide/1-getting-started/quickstart.md) |
| `RUNNING.md` | [docs/guide/1-getting-started/installation.md](guide/1-getting-started/installation.md) |
| `PIPELINE_GUIDE.md` | [docs/guide/1-getting-started/how-to/run-the-pipeline.md](guide/1-getting-started/how-to/README.md) |
| `TEST_APP_README.md` | [docs/guide/1-getting-started/how-to/use-the-ui.md](guide/1-getting-started/how-to/README.md) |

### **Model Documentation**
| Old Location | New Location |
|--------------|--------------|
| `models/implemented/README.md` | [docs/guide/2-models/README.md](guide/2-models/README.md) |
| *(Model schemas in YAML)* | [docs/guide/2-models/implemented/](guide/2-models/implemented/) |

### **Architecture Documentation**
| Old Location | New Location |
|--------------|--------------|
| `ARCHITECTURE_*.md` | [docs/guide/3-architecture/system-design.md](guide/3-architecture/system-design.md) |
| `docs/CODEBASE_ARCHITECTURE_ANALYSIS.md` | [docs/guide/3-architecture/](guide/3-architecture/) |
| `docs/NOTEBOOK_SYSTEM_README.md` | [docs/guide/3-architecture/components/notebook-system/](guide/3-architecture/components/notebook-system/) |
| `docs/FILTER_ARCHITECTURE.md` | [docs/guide/3-architecture/components/core-session/filter-engine.md](guide/3-architecture/components/core-session/filter-engine.md) |
| `docs/STORAGE_*.md` | [docs/guide/3-architecture/components/storage/](guide/3-architecture/components/storage/) |
| `docs/SESSION_*.md` | [docs/guide/3-architecture/components/core-session/](guide/3-architecture/components/core-session/) |

### **Development & Todos**
| Old Location | New Location |
|--------------|--------------|
| `ARCHITECTURE_TODO.md` | [docs/guide/4-development/todo-tracker.md](guide/4-development/todo-tracker.md) |
| `ARCHITECTURE_IMPROVEMENTS.md` | [docs/guide/4-development/roadmap.md](guide/4-development/roadmap.md) |

### **Specialized Guides**
| Old Location | New Location |
|--------------|--------------|
| `CALENDAR_DIMENSION_GUIDE.md` | [docs/guide/2-models/implemented/core-model.md](guide/2-models/implemented/core-model.md) |
| `FORECAST_README.md` | [docs/guide/2-models/implemented/forecast-model.md](guide/2-models/implemented/forecast-model.md) |
| `TESTING_GUIDE.md` | [docs/guide/4-development/](guide/4-development/) |

---

## 🎯 New Structure

```
docs/
├── guide/                          # ← NEW: Consolidated documentation
│   ├── README.md                   # Main entry point
│   ├── 1-getting-started/          # Installation, tutorials, how-tos
│   ├── 2-models/                   # Model documentation
│   ├── 3-architecture/             # System design & components
│   └── 4-development/              # Roadmap, todos, contributing
├── archive/                        # ← OLD: Archived legacy docs
│   ├── session-notes/              # Historical session summaries
│   └── experimental/               # Experimental/refactoring docs
└── MIGRATION_GUIDE.md              # This file
```

---

## ✨ What's New

### **Better Organization**
- **4 clear sections:** Getting Started, Models, Architecture, Development
- **Progressive depth:** Start simple, dive deep as needed
- **Cross-referenced:** Easy navigation between related topics

### **Comprehensive Content**
- **50 markdown files** with detailed documentation
- **30 architecture component docs** covering every subsystem
- **6 model docs** for all implemented models
- **10+ how-to guides** for common tasks

### **Code Examples**
- **5 runnable examples** in `examples/` directory
- **Inline code samples** tested against codebase
- **Real file paths** referenced throughout

### **Better Navigation**
- **Table of contents** in every section
- **Learning paths** for different roles
- **Quick reference** sections
- **Search-friendly** structure

---

## 📚 Key Entry Points

### **New to de_Funk?**
Start here: [docs/guide/1-getting-started/quickstart.md](guide/1-getting-started/quickstart.md)

### **Want Architecture Overview?**
Read: [docs/guide/1-getting-started/architecture-overview.md](guide/1-getting-started/architecture-overview.md)

### **Need Specific How-To?**
Browse: [docs/guide/1-getting-started/how-to/](guide/1-getting-started/how-to/README.md)

### **Understanding Models?**
See: [docs/guide/2-models/](guide/2-models/README.md)

### **Deep Dive into Components?**
Explore: [docs/guide/3-architecture/components/](guide/3-architecture/README.md)

### **Want to Contribute?**
Check: [docs/guide/4-development/](guide/4-development/README.md)

---

## 🔍 Finding Old Content

If you're looking for a specific old document:

1. **Check the table above** for common mappings
2. **Search in** `docs/archive/` for historical docs
3. **Browse** `docs/guide/` for consolidated content
4. **Use git history** to see original content:
   ```bash
   git log --follow --all -- <old-file-path>
   ```

---

## 🚀 Next Steps

1. **Bookmark** [docs/guide/README.md](guide/README.md) as your main documentation entry point
2. **Update** any scripts or tools that reference old docs
3. **Contribute** improvements via the new structure

---

## 💡 Feedback

Found something missing or incorrect?
- Check [docs/guide/4-development/todo-tracker.md](guide/4-development/todo-tracker.md)
- Submit an issue or PR

---

**Migration Completed:** 2024-11-08
**New Docs Location:** `docs/guide/`
**Archived Docs Location:** `docs/archive/`
