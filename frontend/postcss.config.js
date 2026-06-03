// Tailwind is only consumed by the crm section (its index.css has the @tailwind
// directives). Other sections' stylesheets contain no @tailwind at-rules, so the
// Tailwind plugin is a no-op for them; autoprefixer is harmless everywhere.
export default {
  plugins: {
    tailwindcss: {},
    autoprefixer: {},
  },
};
