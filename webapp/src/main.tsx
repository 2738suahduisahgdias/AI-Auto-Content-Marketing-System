import React, { lazy, Suspense } from "react";
import ReactDOM from "react-dom/client";
import { BrowserRouter } from "react-router-dom";
import { AppProvider } from "@/AppContext";
import App from "@/App";
import "@/styles.css";

const DemoWorkbench = lazy(() => import("@/demo/DemoWorkbench"));
const isDemo = /^\/demo(?:\/|$)/.test(window.location.pathname);

ReactDOM.createRoot(document.getElementById("root")!).render(
  <React.StrictMode>{isDemo ? <Suspense fallback={<p>正在打开映序后台预览…</p>}><DemoWorkbench /></Suspense> : <BrowserRouter><AppProvider><App /></AppProvider></BrowserRouter>}</React.StrictMode>,
);
