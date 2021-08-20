import React from "react";
import ReactDOM from "react-dom";
import App from "./App";
import { store } from "./redux/app/store";
import { Provider } from "react-redux";
import { CssBaseline } from "@material-ui/core";
import "@fontsource/roboto";
import Theme from "./Theme";

ReactDOM.render(
  <React.StrictMode>
    <Provider store={store}>
      <Theme>
        <CssBaseline />
        <App />
      </Theme>
    </Provider>
  </React.StrictMode>,
  document.getElementById("root")
);
