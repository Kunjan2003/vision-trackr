import React from "react";
import {createRoot} from "react-dom/client";
import App from "./App";
import Widget from "./Widget";
import "./styles.css";
import "./vision.css";
const widget=new URLSearchParams(window.location.search).get("window")==="widget";
if(widget)document.body.classList.add("widget-window");
createRoot(document.getElementById("root")!).render(<React.StrictMode>{widget?<Widget/>:<App/>}</React.StrictMode>);
