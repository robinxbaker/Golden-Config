import { ReactNode } from "react";
import {
  AppBar,
  Box,
  Chip,
  Drawer,
  List,
  ListItemButton,
  ListItemIcon,
  ListItemText,
  Toolbar,
  Typography,
  Button,
} from "@mui/material";
import RouterIcon from "@mui/icons-material/Router";
import DescriptionIcon from "@mui/icons-material/Description";
import PlayCircleIcon from "@mui/icons-material/PlayCircle";
import ShareIcon from "@mui/icons-material/Share";
import ShieldIcon from "@mui/icons-material/Shield";
import LogoutIcon from "@mui/icons-material/Logout";
import { useLocation, useNavigate } from "react-router-dom";
import { useAuth } from "../auth/AuthContext";

const DRAWER_WIDTH = 232;

const NAV = [
  { to: "/devices", label: "Devices", icon: <RouterIcon /> },
  { to: "/configs", label: "Config Files", icon: <DescriptionIcon /> },
  { to: "/jobs", label: "Jobs", icon: <PlayCircleIcon /> },
  { to: "/shares", label: "Shares", icon: <ShareIcon /> },
];

export function AppLayout({ children }: { children: ReactNode }) {
  const navigate = useNavigate();
  const location = useLocation();
  const { user, logout } = useAuth();

  return (
    <Box sx={{ display: "flex" }}>
      <AppBar position="fixed" sx={{ zIndex: (t) => t.zIndex.drawer + 1 }}>
        <Toolbar>
          <ShieldIcon sx={{ mr: 1, color: "secondary.main" }} />
          <Typography variant="h6" sx={{ flexGrow: 1 }}>
            Golden Config
          </Typography>
          {user && (
            <Chip
              label={`${user.username} · ${user.role}`}
              color="secondary"
              size="small"
              sx={{ mr: 2 }}
            />
          )}
          <Button color="inherit" startIcon={<LogoutIcon />} onClick={logout}>
            Logout
          </Button>
        </Toolbar>
      </AppBar>

      <Drawer
        variant="permanent"
        sx={{
          width: DRAWER_WIDTH,
          flexShrink: 0,
          [`& .MuiDrawer-paper`]: { width: DRAWER_WIDTH, boxSizing: "border-box" },
        }}
      >
        <Toolbar />
        <Box sx={{ overflow: "auto" }}>
          <List>
            {NAV.map((item) => (
              <ListItemButton
                key={item.to}
                selected={location.pathname === item.to}
                onClick={() => navigate(item.to)}
              >
                <ListItemIcon>{item.icon}</ListItemIcon>
                <ListItemText primary={item.label} />
              </ListItemButton>
            ))}
          </List>
        </Box>
      </Drawer>

      <Box component="main" sx={{ flexGrow: 1, p: 3 }}>
        <Toolbar />
        {children}
      </Box>
    </Box>
  );
}
