package core

import (
	"io"
	"os"
	"strings"
)

// IsLoggingDisabled checks if MCP logging should be disabled
func IsLoggingDisabled() bool {
	val := os.Getenv("MCP_DISABLE_LOGGING")
	return strings.ToLower(val) == "true" || val == "1"
}

// GetLogWriter returns the appropriate writer for logging based on configuration
func GetLogWriter() io.Writer {
	if IsLoggingDisabled() {
		return io.Discard
	}
	return os.Stderr
}
