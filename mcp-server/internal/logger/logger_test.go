package logger

import (
	"bytes"
	"errors"
	"testing"

	"github.com/stretchr/testify/assert"
	"go.uber.org/zap"
	"go.uber.org/zap/zapcore"
	"go.uber.org/zap/zaptest"
)

// captureOutput captures log output during a test
func captureOutput(f func()) string {
	var buf bytes.Buffer

	// Create a custom zap logger that writes to our buffer
	encoderConfig := zap.NewDevelopmentEncoderConfig()
	encoder := zapcore.NewConsoleEncoder(encoderConfig)
	core := zapcore.NewCore(encoder, zapcore.AddSync(&buf), zapcore.DebugLevel)

	oldLogger := zapLogger
	zapLogger = zap.New(core)
	defer func() { zapLogger = oldLogger }()

	f()
	return buf.String()
}

func TestSetLogLevel(t *testing.T) {
	tests := []struct {
		level    string
		expected Level
	}{
		{"debug", LevelDebug},
		{"DEBUG", LevelDebug},
		{"info", LevelInfo},
		{"INFO", LevelInfo},
		{"warn", LevelWarn},
		{"WARN", LevelWarn},
		{"error", LevelError},
		{"ERROR", LevelError},
		{"unknown", LevelInfo}, // Default
	}

	for _, tt := range tests {
		t.Run(tt.level, func(t *testing.T) {
			setLogLevel(tt.level)
			assert.Equal(t, tt.expected, logLevel)
		})
	}
}

func TestZapLevelConversion(t *testing.T) {
	tests := []struct {
		level         Level
		expectedLevel zapcore.Level
	}{
		{LevelDebug, zapcore.DebugLevel},
		{LevelInfo, zapcore.InfoLevel},
		{LevelWarn, zapcore.WarnLevel},
		{LevelError, zapcore.ErrorLevel},
	}

	for _, tt := range tests {
		t.Run(zapcore.Level(tt.expectedLevel).String(), func(t *testing.T) {
			atomicLevel := getZapLevel(tt.level)
			assert.Equal(t, tt.expectedLevel, atomicLevel.Level())
		})
	}
}

func TestDebug(t *testing.T) {
	// Setup test logger
	zapLogger = zaptest.NewLogger(t)

	// Test when debug is enabled
	logLevel = LevelDebug
	output := captureOutput(func() {
		Debug("Test debug message: %s", "value")
	})
	assert.Contains(t, output, "DEBUG")
	assert.Contains(t, output, "Test debug message: value")

	// Test when debug is disabled
	logLevel = LevelInfo
	output = captureOutput(func() {
		Debug("This should not appear")
	})
	assert.Empty(t, output)
}

func TestInfo(t *testing.T) {
	// Setup test logger
	zapLogger = zaptest.NewLogger(t)

	// Test when info is enabled
	logLevel = LevelInfo
	output := captureOutput(func() {
		Info("Test info message: %s", "value")
	})
	assert.Contains(t, output, "INFO")
	assert.Contains(t, output, "Test info message: value")

	// Test when info is disabled
	logLevel = LevelError
	output = captureOutput(func() {
		Info("This should not appear")
	})
	assert.Empty(t, output)
}

func TestWarn(t *testing.T) {
	// Setup test logger
	zapLogger = zaptest.NewLogger(t)

	// Test when warn is enabled
	logLevel = LevelWarn
	output := captureOutput(func() {
		Warn("Test warn message: %s", "value")
	})
	assert.Contains(t, output, "WARN")
	assert.Contains(t, output, "Test warn message: value")

	// Test when warn is disabled
	logLevel = LevelError
	output = captureOutput(func() {
		Warn("This should not appear")
	})
	assert.Empty(t, output)
}

func TestError(t *testing.T) {
	// Setup test logger
	zapLogger = zaptest.NewLogger(t)

	// Error should always be logged when level is error
	logLevel = LevelError
	output := captureOutput(func() {
		Error("Test error message: %s", "value")
	})
	assert.Contains(t, output, "ERROR")
	assert.Contains(t, output, "Test error message: value")
}

func TestErrorWithStack(t *testing.T) {
	// Setup test logger
	zapLogger = zaptest.NewLogger(t)

	err := errors.New("test error")
	output := captureOutput(func() {
		ErrorWithStack(err)
	})
	assert.Contains(t, output, "ERROR")
	assert.Contains(t, output, "test error")
	assert.Contains(t, output, "stack")
}

// For the structured logging tests, we'll just test that the functions don't panic

func TestRequestLog(t *testing.T) {
	zapLogger = zaptest.NewLogger(t)
	logLevel = LevelDebug
	assert.NotPanics(t, func() {
		RequestLog("POST", "/api/data", "session123", `{"key":"value"}`)
	})
}

func TestResponseLog(t *testing.T) {
	zapLogger = zaptest.NewLogger(t)
	logLevel = LevelDebug
	assert.NotPanics(t, func() {
		ResponseLog(200, "session123", `{"result":"success"}`)
	})
}

func TestSSEEventLog(t *testing.T) {
	zapLogger = zaptest.NewLogger(t)
	logLevel = LevelDebug
	assert.NotPanics(t, func() {
		SSEEventLog("message", "session123", `{"data":"content"}`)
	})
}

func TestRequestResponseLog(t *testing.T) {
	zapLogger = zaptest.NewLogger(t)
	logLevel = LevelDebug
	assert.NotPanics(t, func() {
		RequestResponseLog("RPC", "session123", `{"method":"getData"}`, `{"result":"data"}`)
	})
}
