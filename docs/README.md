# REAG Fraud Investigation Toolkit - GitHub Pages

This directory contains the GitHub Pages website for the REAG Fraud Investigation Toolkit.

## 🌐 Live Site

Visit: [https://pedrodnt.github.io/REAG/](https://pedrodnt.github.io/REAG/)

## 📁 Structure

```
docs/
├── index.html              # Homepage
├── methodologies.html      # Detection methods documentation
├── results.html           # Investigation findings
├── user-guide.html        # Step-by-step user guide
├── technical.html         # Technical documentation
├── about.html             # About the project
├── _config.yml            # Jekyll configuration
├── assets/
│   ├── css/
│   │   └── main.css       # Main stylesheet
│   ├── js/
│   │   ├── main.js        # Core functionality
│   │   └── charts.js      # Data visualizations
│   ├── img/               # Images and diagrams
│   └── data/              # Sample data for demos
└── README.md              # This file
```

## 🚀 Local Development

### Using Python's built-in server:

```bash
cd docs
python -m http.server 8000
```

Then visit: `http://localhost:8000`

### Using Jekyll (optional):

```bash
cd docs
bundle install
bundle exec jekyll serve
```

Then visit: `http://localhost:4000/REAG/`

## 🎨 Design System

### Colors
- **Primary**: #1e3a8a (Deep Blue)
- **Secondary**: #0891b2 (Teal)
- **Accent**: #3b82f6 (Bright Blue)
- **Success**: #16a34a (Green)
- **Warning**: #f59e0b (Amber)
- **Danger**: #dc2626 (Red)

### Typography
- **Headers**: System fonts (Inter, Roboto, Segoe UI)
- **Body**: System font stack
- **Code**: Fira Code, Consolas, Monaco

### Responsive Breakpoints
- **Mobile**: < 768px
- **Tablet**: 768px - 1024px
- **Desktop**: > 1024px

## 📝 Content

### Pages Overview

1. **Homepage** (`index.html`)
   - Hero section with key statistics
   - Overview cards
   - Methods preview
   - Real-world impact examples
   - Quick start guide

2. **Methodologies** (`methodologies.html`)
   - Statistical analysis methods
   - Benford's Law
   - Phantom assets detection
   - Fraud schemes identification
   - Performance benchmarks

3. **Results** (`results.html`)
   - Anonymized investigation findings
   - Case studies
   - Interactive visualizations
   - Effectiveness metrics

4. **User Guide** (`user-guide.html`)
   - Installation instructions
   - Step-by-step workflows
   - Code examples
   - Troubleshooting

5. **Technical Documentation** (`technical.html`)
   - Architecture overview
   - API reference
   - Data sources
   - Developer guide

6. **About** (`about.html`)
   - Project background
   - Team
   - Contributing guidelines
   - License information

## 🔧 Technologies

- **HTML5**: Semantic markup
- **CSS3**: Custom design system (no framework)
- **JavaScript**: Vanilla JS (no dependencies)
- **Chart.js**: Data visualizations (optional, CDN)
- **Font Awesome**: Icons (CDN)
- **Jekyll**: Static site generation (optional)

## ✨ Features

- ✅ Fully responsive design
- ✅ Mobile-first approach
- ✅ Accessible (WCAG AA)
- ✅ Fast loading (< 2s)
- ✅ SEO optimized
- ✅ Print-friendly
- ✅ Progressive enhancement
- ✅ No external dependencies (core functionality)

## 🚀 Deployment

### Automatic Deployment

GitHub Pages automatically deploys from the `docs/` directory when:
1. Changes are pushed to the main branch
2. GitHub Pages is enabled in repository settings
3. Source is set to "Deploy from branch" → "main" → "/docs"

### Manual Deployment

1. Make changes to files in `docs/`
2. Test locally
3. Commit and push to main branch
4. Site updates automatically (may take 1-2 minutes)

## 📊 Analytics

To add analytics, update `_config.yml`:

```yaml
google_analytics: UA-XXXXXXXXX-X
```

Or add your preferred analytics code to the `<head>` section of each page.

## 🎯 SEO Checklist

- [x] Meta titles and descriptions
- [x] Open Graph tags
- [x] Semantic HTML structure
- [x] Alt text for images
- [x] Sitemap.xml
- [x] robots.txt
- [x] Mobile-friendly
- [x] Fast loading times

## 🤝 Contributing

To contribute to the website:

1. Fork the repository
2. Create a branch: `git checkout -b feature/new-page`
3. Make changes in the `docs/` directory
4. Test locally
5. Commit: `git commit -m "Add new page"`
6. Push: `git push origin feature/new-page`
7. Open a Pull Request

## 📄 License

MIT License - Same as the main project

## 🔗 Links

- **Main Repository**: [github.com/PedroDnT/REAG](https://github.com/PedroDnT/REAG)
- **Live Site**: [pedrodnt.github.io/REAG](https://pedrodnt.github.io/REAG/)
- **Issues**: [github.com/PedroDnT/REAG/issues](https://github.com/PedroDnT/REAG/issues)

## 📞 Support

For website-specific issues:
1. Check the browser console for errors
2. Test in different browsers
3. Verify local development works
4. Open an issue with details

## 🎨 Customization

### Changing Colors

Edit CSS variables in `assets/css/main.css`:

```css
:root {
    --primary-color: #1e3a8a;
    --secondary-color: #0891b2;
    /* ... */
}
```

### Adding Pages

1. Create new HTML file in `docs/`
2. Use existing pages as templates
3. Add navigation link in all pages
4. Update sitemap

### Modifying Layout

- Navigation: Edit in each HTML file (or create `_includes/nav.html` if using Jekyll)
- Footer: Edit in each HTML file
- Styles: Modify `assets/css/main.css`
- Scripts: Modify `assets/js/main.js`

## 📱 Browser Support

- ✅ Chrome/Edge (last 2 versions)
- ✅ Firefox (last 2 versions)
- ✅ Safari (last 2 versions)
- ✅ Mobile browsers (iOS Safari, Chrome Mobile)
- ⚠️ IE11 (basic functionality only)

## ⚡ Performance

Target metrics:
- First Contentful Paint: < 1.5s
- Time to Interactive: < 3.5s
- Cumulative Layout Shift: < 0.1
- Lighthouse Score: > 90

Optimization techniques:
- Minified CSS/JS
- Optimized images
- Lazy loading
- CDN for external libraries
- Caching headers

---

**Last Updated**: 2026-04-10
**Maintainer**: REAG Investigation Team
