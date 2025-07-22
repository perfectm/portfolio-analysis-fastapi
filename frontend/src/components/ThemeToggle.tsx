import React from "react";
import { IconButton, Tooltip } from "@mui/material";
import { Brightness4, Brightness7 } from "@mui/icons-material";
import { useTheme } from "../contexts/ThemeContext";

interface ThemeToggleProps {
  size?: "small" | "medium" | "large";
  showTooltip?: boolean;
}

export const ThemeToggle: React.FC<ThemeToggleProps> = ({
  size = "medium",
  showTooltip = true,
}) => {
  const { mode, toggleTheme } = useTheme();

  const button = (
    <IconButton
      onClick={toggleTheme}
      size={size}
      sx={{
        transition: "all 0.2s ease-in-out",
        "&:hover": {
          transform: "scale(1.1)",
        },
      }}
      aria-label={`Switch to ${mode === "light" ? "dark" : "light"} mode`}
    >
      {mode === "light" ? (
        <Brightness4
          sx={{ fontSize: size === "large" ? 28 : size === "small" ? 20 : 24 }}
        />
      ) : (
        <Brightness7
          sx={{ fontSize: size === "large" ? 28 : size === "small" ? 20 : 24 }}
        />
      )}
    </IconButton>
  );

  if (showTooltip) {
    return (
      <Tooltip
        title={`Switch to ${mode === "light" ? "dark" : "light"} mode`}
        arrow
        placement="bottom"
      >
        {button}
      </Tooltip>
    );
  }

  return button;
};
