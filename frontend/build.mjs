import * as esbuild from "esbuild";

const watch = process.argv.includes("--watch");

const options = {
  entryPoints: ["src/main.ts"],
  bundle: true,
  format: "esm",
  outfile: "../provenance_widget/static/widget.js",
  minify: !watch,
  sourcemap: watch,
  loader: { ".css": "css" },
};

if (watch) {
  const ctx = await esbuild.context(options);
  await ctx.watch();
  console.log("watching...");
} else {
  await esbuild.build(options);
  console.log("build complete");
}
