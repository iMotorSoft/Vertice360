/* Tailwind config for Pozo360 Astro + Svelte */
module.exports = {
  content: ["./src/**/*.{astro,html,js,jsx,ts,tsx,svelte}"],
  theme: {
    extend: {
      colors: {
        brand: {
          primary: "var(--brand-primary)",
          secondary: "var(--brand-secondary)",
          accent: "var(--brand-accent)",
        },
      },
    },
  },
  plugins: [require("daisyui")],
  daisyui: {
    themes: [
      {
        pozo360: {
          primary: "var(--brand-primary)",
          secondary: "var(--brand-secondary)",
          accent: "var(--brand-accent)",
          neutral: "#1f2937",
          "base-100": "#f8fafc",
        },
      },
    ],
  },
};
