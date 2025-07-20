/// <reference types="vite/client" />

interface ImportMetaEnv {
  readonly VITE_API_URL: string
}

interface ImportMeta {
  readonly env: ImportMetaEnv
}

// Type declarations for CSS and asset imports
declare module "*.css" {
  const content: any;
  export default content;
}

declare module "*.module.css" {
  const classes: any;
  export default classes;
}

declare module "*.scss" {
  const content: any;
  export default content;
}

declare module "*.module.scss" {
  const classes: any;
  export default classes;
}

declare module "*.svg" {
  const src: string;
  export default src;
}

declare module "*.png" {
  const src: string;
  export default src;
}

declare module "*.jpg" {
  const src: string;
  export default src;
}

declare module "*.jpeg" {
  const src: string;
  export default src;
}

declare module "*.gif" {
  const src: string;
  export default src;
}

declare module "*.webp" {
  const src: string;
  export default src;
}