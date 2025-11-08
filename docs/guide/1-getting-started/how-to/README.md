# How-To Guides

Step-by-step tutorials for common tasks in de_Funk.

---

## Overview

This section provides practical, task-oriented guides for:

- **Data Engineering** - Ingestion, transformation, model building
- **Analytics** - Notebooks, queries, visualization
- **Development** - Extending and customizing the platform

**Guide format:**
- **Goal** - What you'll accomplish
- **Prerequisites** - What you need before starting
- **Steps** - Numbered instructions with commands
- **Examples** - Real code you can run
- **Troubleshooting** - Common issues and solutions

---

## 📊 Data Engineering Guides

### [Run the Pipeline](run-the-pipeline.md)

Execute data ingestion and transformation pipelines.

**What you'll learn:**
- Run the full pipeline (ingestion + transformation + forecasting)
- Run individual pipeline components
- Schedule automated runs
- Monitor pipeline progress
- Handle errors and retries

**Use cases:**
- Daily data refresh
- Historical backfill
- Testing with sample data
- Production deployment

**Difficulty:** Beginner
**Time:** 15 minutes

---

### [Create a Facet](create-a-facet.md)

Add new data source transformations.

**What you'll learn:**
- Understand the Facet pattern
- Create a custom facet class
- Define schema transformations
- Register facets with providers
- Test facet transformations

**Use cases:**
- Integrate new API endpoints
- Normalize API responses
- Add data validation
- Custom data transformations

**Difficulty:** Intermediate
**Time:** 30 minutes

---

### [Create an API Provider](create-an-api-provider.md)

Integrate new external APIs.

**What you'll learn:**
- Implement a provider class
- Handle authentication
- Manage pagination
- Rate limit handling
- Error handling and retries

**Use cases:**
- Add new data sources (Alpha Vantage, Yahoo Finance, etc.)
- Custom internal APIs
- Webhook integrations
- Real-time data feeds

**Difficulty:** Intermediate
**Time:** 45 minutes

---

### [Create a Model](create-a-model.md)

Build dimensional data models.

**What you'll learn:**
- Define model schema in YAML
- Create dimensions and facts
- Define graph transformations (nodes, edges, paths)
- Define measures and calculations
- Build and test models

**Use cases:**
- Add business domain models (HR, Operations, etc.)
- Custom dimensional schemas
- Cross-model relationships
- Derived metrics

**Difficulty:** Advanced
**Time:** 60 minutes

---

## 📈 Analytics Guides

### [Create a Notebook](create-a-notebook.md)

Build interactive analytics dashboards.

**What you'll learn:**
- Markdown notebook format
- YAML front matter
- Inline filters (`$filter${}`)
- Inline exhibits (`$exhibits${}`)
- Layout and organization

**Use cases:**
- Custom dashboards
- Executive reports
- Exploratory analysis
- Shareable analytics

**Difficulty:** Beginner
**Time:** 20 minutes

---

### [Work with Session Data](work-with-session-data.md)

Adhoc data analysis techniques.

**What you'll learn:**
- UniversalSession API
- Query models and tables
- Apply filters programmatically
- Cross-model queries
- Export data to pandas

**Use cases:**
- Scripted analysis
- Custom reports
- Data validation
- Integration with Jupyter notebooks

**Difficulty:** Intermediate
**Time:** 30 minutes

---

### [Use the UI](use-the-ui.md)

Navigate and use the Streamlit interface.

**What you'll learn:**
- Navigate the sidebar
- Open and manage notebooks
- Apply filters
- Interact with exhibits (charts, tables)
- Toggle edit/view mode
- Download data

**Use cases:**
- Interactive exploration
- Business intelligence
- Sharing insights
- Presentation mode

**Difficulty:** Beginner
**Time:** 10 minutes

---

## 🎨 Visualization Guides

### [Create Custom Exhibits](create-custom-exhibits.md)

Add new visualization types.

**What you'll learn:**
- Exhibit component architecture
- Create custom exhibit renderers
- Define exhibit schemas
- Register new exhibit types
- Test and debug exhibits

**Use cases:**
- Custom chart types
- Business-specific visualizations
- Interactive widgets
- Third-party chart libraries

**Difficulty:** Advanced
**Time:** 45 minutes

---

### [Customize Themes](customize-themes.md)

Customize UI appearance and branding.

**What you'll learn:**
- Theme configuration
- Custom color schemes
- Logo and branding
- CSS customization
- Responsive design

**Use cases:**
- Corporate branding
- Custom color palettes
- Accessibility improvements
- White-label deployments

**Difficulty:** Intermediate
**Time:** 30 minutes

---

## 🔧 Development Guides

### [Extend the Session API](extend-the-session-api.md)

Add custom session functionality.

**What you'll learn:**
- UniversalSession architecture
- Add custom methods
- Connection abstraction
- Backend-specific optimizations
- Testing strategies

**Use cases:**
- Custom query methods
- Performance optimization
- Multi-tenant support
- Audit logging

**Difficulty:** Advanced
**Time:** 60 minutes

---

### [Add a Backend Connection](add-a-backend-connection.md)

Integrate new query engines.

**What you'll learn:**
- DataConnection interface
- Implement connection class
- Query translation
- Type conversions
- Filter application

**Use cases:**
- PostgreSQL backend
- ClickHouse backend
- Snowflake backend
- Custom databases

**Difficulty:** Advanced
**Time:** 90 minutes

---

### [Write Tests](write-tests.md)

Test your code and integrations.

**What you'll learn:**
- Test structure and conventions
- Unit tests for facets
- Integration tests for models
- UI tests with Streamlit
- Mock external APIs

**Use cases:**
- Ensure code quality
- Prevent regressions
- CI/CD integration
- Test-driven development

**Difficulty:** Intermediate
**Time:** 45 minutes

---

## 🚀 Deployment Guides

### [Deploy to Production](deploy-to-production.md)

Production deployment strategies.

**What you'll learn:**
- Server requirements
- Docker deployment
- Systemd services
- Nginx reverse proxy
- SSL/TLS setup
- Monitoring and logging

**Use cases:**
- Production deployment
- Scalable infrastructure
- High availability
- Security hardening

**Difficulty:** Advanced
**Time:** 90 minutes

---

### [Configure Scheduled Jobs](configure-scheduled-jobs.md)

Automate pipeline execution.

**What you'll learn:**
- Cron job setup
- Error handling
- Log management
- Alert notifications
- Job monitoring

**Use cases:**
- Daily data refresh
- Weekly reports
- Automated backups
- Maintenance tasks

**Difficulty:** Intermediate
**Time:** 30 minutes

---

### [Monitor Performance](monitor-performance.md)

Performance monitoring and optimization.

**What you'll learn:**
- Query profiling
- Memory usage analysis
- Bottleneck identification
- Optimization techniques
- Monitoring tools

**Use cases:**
- Performance tuning
- Capacity planning
- Troubleshooting slowness
- Cost optimization

**Difficulty:** Advanced
**Time:** 60 minutes

---

## 🎓 Learning Paths

### Path 1: New User → First Dashboard (30 min)

1. [Use the UI](use-the-ui.md) - Learn the interface (10 min)
2. [Create a Notebook](create-a-notebook.md) - Build your first dashboard (20 min)

**Goal:** Create and view your first custom dashboard

---

### Path 2: Data Engineer → Production Pipeline (2 hours)

1. [Run the Pipeline](run-the-pipeline.md) - Understand pipeline execution (15 min)
2. [Create a Facet](create-a-facet.md) - Add data transformations (30 min)
3. [Create an API Provider](create-an-api-provider.md) - Integrate APIs (45 min)
4. [Configure Scheduled Jobs](configure-scheduled-jobs.md) - Automate (30 min)

**Goal:** Deploy an automated data pipeline

---

### Path 3: Analyst → Advanced Analytics (1.5 hours)

1. [Use the UI](use-the-ui.md) - Learn the interface (10 min)
2. [Create a Notebook](create-a-notebook.md) - Build dashboards (20 min)
3. [Work with Session Data](work-with-session-data.md) - Adhoc queries (30 min)
4. [Create Custom Exhibits](create-custom-exhibits.md) - Custom viz (30 min)

**Goal:** Master analytics capabilities

---

### Path 4: Developer → Platform Extension (3+ hours)

1. [Create a Model](create-a-model.md) - Data modeling (60 min)
2. [Extend the Session API](extend-the-session-api.md) - Custom API (60 min)
3. [Write Tests](write-tests.md) - Testing (45 min)
4. [Add a Backend Connection](add-a-backend-connection.md) - New backend (90 min)

**Goal:** Extend the platform with custom functionality

---

## 📋 Guide Templates

### Quick Reference Template

Every guide follows this structure:

```markdown
# [Task Name]

[One-sentence description]

## Goal

What you'll accomplish by following this guide.

## Prerequisites

- Required knowledge
- Required software/tools
- Required configuration

## Steps

### Step 1: [Step Name]

[Detailed instructions]

```bash
# Commands to run
```

[Expected output]

### Step 2: [Step Name]

...

## Examples

### Example 1: [Use Case]

[Complete working example]

## Troubleshooting

### Issue 1: [Problem]

**Symptom:** [What you see]

**Cause:** [Why it happens]

**Solution:**
```bash
# How to fix
```

## Next Steps

- Related guides
- Advanced topics
```

---

## 🆘 Getting Help

**Before you start:**
1. Review the relevant guide prerequisites
2. Ensure your installation is complete ([Installation Guide](../installation.md))
3. Have the documentation open for reference

**While following a guide:**
1. Read each step completely before executing
2. Run commands one at a time
3. Verify expected output matches
4. Check troubleshooting section if issues arise

**If you get stuck:**
1. Review the troubleshooting section in the guide
2. Check the [Installation Guide](../installation.md) troubleshooting
3. Consult the [Architecture Overview](../architecture-overview.md) for context
4. Search existing GitHub issues
5. Open a new issue with details

---

## 🔍 Guide Status

| Guide | Status | Last Updated |
|-------|--------|--------------|
| Run the Pipeline | ✅ Available | 2024-11-08 |
| Create a Facet | 📝 Draft | - |
| Create an API Provider | 📝 Draft | - |
| Create a Model | 📝 Draft | - |
| Create a Notebook | ✅ Available | 2024-11-08 |
| Work with Session Data | 📝 Draft | - |
| Use the UI | ✅ Available | 2024-11-08 |
| Create Custom Exhibits | 📋 Planned | - |
| Customize Themes | 📋 Planned | - |
| Extend the Session API | 📋 Planned | - |
| Add a Backend Connection | 📋 Planned | - |
| Write Tests | 📋 Planned | - |
| Deploy to Production | 📋 Planned | - |
| Configure Scheduled Jobs | 📋 Planned | - |
| Monitor Performance | 📋 Planned | - |

**Legend:**
- ✅ Available - Guide is complete and ready to use
- 📝 Draft - Guide is being written
- 📋 Planned - Guide is planned for future

---

## 💡 Contributing Guides

Want to contribute a guide?

**Guide requirements:**
1. **Tested** - All commands and code must be tested
2. **Complete** - Include all steps, examples, troubleshooting
3. **Clear** - Use simple language and clear formatting
4. **Practical** - Focus on real-world use cases
5. **Linked** - Reference related guides and docs

**Submission process:**
1. Use the guide template above
2. Test all commands and code
3. Include screenshots where helpful
4. Submit pull request
5. Address review comments

---

## 📚 Additional Resources

### Related Documentation

- **[Quickstart Guide](../quickstart.md)** - Get started in 5 minutes
- **[Architecture Overview](../architecture-overview.md)** - Understand the system
- **[Installation Guide](../installation.md)** - Complete setup

### External Resources

- **[Streamlit Documentation](https://docs.streamlit.io/)** - UI framework
- **[DuckDB Documentation](https://duckdb.org/docs/)** - Analytics engine
- **[Plotly Documentation](https://plotly.com/python/)** - Visualization
- **[PySpark Documentation](https://spark.apache.org/docs/latest/api/python/)** - ETL engine (optional)

### Community

- **GitHub Repository** - Source code and issues
- **Discussions** - Ask questions, share insights
- **Wiki** - Community-contributed guides

---

## 🎯 Quick Links

**Most Popular Guides:**
- [Run the Pipeline](run-the-pipeline.md) - Start here for data ingestion
- [Create a Notebook](create-a-notebook.md) - Build your first dashboard
- [Use the UI](use-the-ui.md) - Learn the interface

**For Data Engineers:**
- [Create a Facet](create-a-facet.md)
- [Create an API Provider](create-an-api-provider.md)
- [Create a Model](create-a-model.md)

**For Analysts:**
- [Work with Session Data](work-with-session-data.md)
- [Create a Notebook](create-a-notebook.md)
- [Use the UI](use-the-ui.md)

**For Developers:**
- [Extend the Session API](extend-the-session-api.md)
- [Add a Backend Connection](add-a-backend-connection.md)
- [Write Tests](write-tests.md)

---

## 📝 Feedback

Help us improve these guides!

**What's working well?**
**What's confusing?**
**What's missing?**

Submit feedback via GitHub issues or discussions.

---

**Ready to start?** Pick a guide above or follow a learning path!

**Need help choosing?**
- New to de_Funk? Start with [Use the UI](use-the-ui.md)
- Want to ingest data? Start with [Run the Pipeline](run-the-pipeline.md)
- Want to build dashboards? Start with [Create a Notebook](create-a-notebook.md)

---

**Last Updated:** 2024-11-08
**Guides Available:** 7 / 15
**In Progress:** 4
**Planned:** 4
