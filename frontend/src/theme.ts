import { createTheme } from "@mui/material/styles";

export const theme = createTheme({
  palette: {
    mode: "light",
    primary: { main: "#1f6feb" },
    secondary: { main: "#f5b301" },
    background: { default: "#f4f6fa" },
  },
  shape: { borderRadius: 10 },
  typography: {
    fontFamily: ['"Segoe UI"', "Roboto", "Helvetica", "Arial", "sans-serif"].join(","),
    h5: { fontWeight: 600 },
    h6: { fontWeight: 600 },
  },
});
