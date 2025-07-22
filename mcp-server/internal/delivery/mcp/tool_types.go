package mcp

import (
	"context"
	"fmt"
	"strings"

	"github.com/FreePeak/cortex/pkg/server"
	"github.com/FreePeak/cortex/pkg/tools"
)

// createTextResponse creates a simple response with a text content
func createTextResponse(text string) map[string]interface{} {
	return map[string]interface{}{
		"content": []map[string]interface{}{
			{
				"type": "text",
				"text": text,
			},
		},
	}
}

// addMetadata adds metadata to a response
func addMetadata(resp map[string]interface{}, key string, value interface{}) map[string]interface{} {
	if resp["metadata"] == nil {
		resp["metadata"] = make(map[string]interface{})
	}

	metadata, ok := resp["metadata"].(map[string]interface{})
	if !ok {
		// Create a new metadata map if conversion fails
		metadata = make(map[string]interface{})
		resp["metadata"] = metadata
	}

	metadata[key] = value
	return resp
}

// TODO: Refactor tool type implementations to reduce duplication and improve maintainability
// TODO: Consider using a code generation approach for repetitive tool patterns
// TODO: Add comprehensive request validation for all tool parameters
// TODO: Implement proper rate limiting and resource protection
// TODO: Add detailed documentation for each tool type and its parameters

// ToolType interface defines the structure for different types of database tools
type ToolType interface {
	// GetName returns the base name of the tool type (e.g., "query", "execute")
	GetName() string

	// GetDescription returns a description for this tool type
	GetDescription(dbID string) string

	// CreateTool creates a tool with the specified name
	// The returned tool must be compatible with server.MCPServer.AddTool's first parameter
	CreateTool(name string, dbID string) interface{}

	// HandleRequest handles tool requests for this tool type
	HandleRequest(ctx context.Context, request server.ToolCallRequest, dbID string, useCase UseCaseProvider) (interface{}, error)
}

// UseCaseProvider interface abstracts database use case operations
type UseCaseProvider interface {
	ExecuteQuery(ctx context.Context, dbID, query string, params []interface{}) (string, error)
	ExecuteStatement(ctx context.Context, dbID, statement string, params []interface{}) (string, error)
	ExecuteTransaction(ctx context.Context, dbID, action string, txID string, statement string, params []interface{}, readOnly bool) (string, map[string]interface{}, error)
	GetDatabaseInfo(dbID string) (map[string]interface{}, error)
	ListDatabases() []string
	GetDatabaseType(dbID string) (string, error)
}

// BaseToolType provides common functionality for tool types
type BaseToolType struct {
	name        string
	description string
}

// GetName returns the name of the tool type
func (b *BaseToolType) GetName() string {
	return b.name
}

// GetDescription returns a description for the tool type
func (b *BaseToolType) GetDescription(dbID string) string {
	return fmt.Sprintf("%s on %s database", b.description, dbID)
}

//------------------------------------------------------------------------------
// QueryTool implementation
//------------------------------------------------------------------------------

// QueryTool handles SQL query operations
type QueryTool struct {
	BaseToolType
}

// NewQueryTool creates a new query tool type
func NewQueryTool() *QueryTool {
	return &QueryTool{
		BaseToolType: BaseToolType{
			name:        "query",
			description: "Execute SQL query",
		},
	}
}

// CreateTool creates a query tool
func (t *QueryTool) CreateTool(name string, dbID string) interface{} {
	return tools.NewTool(
		name,
		tools.WithDescription(t.GetDescription(dbID)),
		tools.WithString("query",
			tools.Description("SQL query to execute"),
			tools.Required(),
		),
		tools.WithArray("params",
			tools.Description("Query parameters"),
			tools.Items(map[string]interface{}{"type": "string"}),
		),
	)
}

// HandleRequest handles query tool requests
func (t *QueryTool) HandleRequest(ctx context.Context, request server.ToolCallRequest, dbID string, useCase UseCaseProvider) (interface{}, error) {
	// If dbID is not provided, extract it from the tool name
	if dbID == "" {
		dbID = extractDatabaseIDFromName(request.Name)
	}

	query, ok := request.Parameters["query"].(string)
	if !ok {
		return nil, fmt.Errorf("query parameter must be a string")
	}

	var queryParams []interface{}
	if request.Parameters["params"] != nil {
		if paramsArr, ok := request.Parameters["params"].([]interface{}); ok {
			queryParams = paramsArr
		}
	}

	result, err := useCase.ExecuteQuery(ctx, dbID, query, queryParams)
	if err != nil {
		return nil, err
	}

	return createTextResponse(result), nil
}

// extractDatabaseIDFromName extracts the database ID from a tool name
func extractDatabaseIDFromName(name string) string {
	// Format is: <tooltype>_<dbID>
	parts := strings.Split(name, "_")
	if len(parts) < 2 {
		return ""
	}

	// The database ID is the last part
	return parts[len(parts)-1]
}

//------------------------------------------------------------------------------
// ExecuteTool implementation
//------------------------------------------------------------------------------

// ExecuteTool handles SQL statement execution
type ExecuteTool struct {
	BaseToolType
}

// NewExecuteTool creates a new execute tool type
func NewExecuteTool() *ExecuteTool {
	return &ExecuteTool{
		BaseToolType: BaseToolType{
			name:        "execute",
			description: "Execute SQL statement",
		},
	}
}

// CreateTool creates an execute tool
func (t *ExecuteTool) CreateTool(name string, dbID string) interface{} {
	return tools.NewTool(
		name,
		tools.WithDescription(t.GetDescription(dbID)),
		tools.WithString("statement",
			tools.Description("SQL statement to execute (INSERT, UPDATE, DELETE, etc.)"),
			tools.Required(),
		),
		tools.WithArray("params",
			tools.Description("Statement parameters"),
			tools.Items(map[string]interface{}{"type": "string"}),
		),
	)
}

// HandleRequest handles execute tool requests
func (t *ExecuteTool) HandleRequest(ctx context.Context, request server.ToolCallRequest, dbID string, useCase UseCaseProvider) (interface{}, error) {
	// If dbID is not provided, extract it from the tool name
	if dbID == "" {
		dbID = extractDatabaseIDFromName(request.Name)
	}

	statement, ok := request.Parameters["statement"].(string)
	if !ok {
		return nil, fmt.Errorf("statement parameter must be a string")
	}

	var statementParams []interface{}
	if request.Parameters["params"] != nil {
		if paramsArr, ok := request.Parameters["params"].([]interface{}); ok {
			statementParams = paramsArr
		}
	}

	result, err := useCase.ExecuteStatement(ctx, dbID, statement, statementParams)
	if err != nil {
		return nil, err
	}

	return createTextResponse(result), nil
}

//------------------------------------------------------------------------------
// TransactionTool implementation
//------------------------------------------------------------------------------

// TransactionTool handles database transactions
type TransactionTool struct {
	BaseToolType
}

// NewTransactionTool creates a new transaction tool type
func NewTransactionTool() *TransactionTool {
	return &TransactionTool{
		BaseToolType: BaseToolType{
			name:        "transaction",
			description: "Manage transactions",
		},
	}
}

// CreateTool creates a transaction tool
func (t *TransactionTool) CreateTool(name string, dbID string) interface{} {
	return tools.NewTool(
		name,
		tools.WithDescription(t.GetDescription(dbID)),
		tools.WithString("action",
			tools.Description("Transaction action (begin, commit, rollback, execute)"),
			tools.Required(),
		),
		tools.WithString("transactionId",
			tools.Description("Transaction ID (required for commit, rollback, execute)"),
		),
		tools.WithString("statement",
			tools.Description("SQL statement to execute within transaction (required for execute)"),
		),
		tools.WithArray("params",
			tools.Description("Statement parameters"),
			tools.Items(map[string]interface{}{"type": "string"}),
		),
		tools.WithBoolean("readOnly",
			tools.Description("Whether the transaction is read-only (for begin)"),
		),
	)
}

// HandleRequest handles transaction tool requests
func (t *TransactionTool) HandleRequest(ctx context.Context, request server.ToolCallRequest, dbID string, useCase UseCaseProvider) (interface{}, error) {
	// If dbID is not provided, extract it from the tool name
	if dbID == "" {
		dbID = extractDatabaseIDFromName(request.Name)
	}

	action, ok := request.Parameters["action"].(string)
	if !ok {
		return nil, fmt.Errorf("action parameter must be a string")
	}

	txID := ""
	if request.Parameters["transactionId"] != nil {
		var ok bool
		txID, ok = request.Parameters["transactionId"].(string)
		if !ok {
			return nil, fmt.Errorf("transactionId parameter must be a string")
		}
	}

	statement := ""
	if request.Parameters["statement"] != nil {
		var ok bool
		statement, ok = request.Parameters["statement"].(string)
		if !ok {
			return nil, fmt.Errorf("statement parameter must be a string")
		}
	}

	var params []interface{}
	if request.Parameters["params"] != nil {
		if paramsArr, ok := request.Parameters["params"].([]interface{}); ok {
			params = paramsArr
		}
	}

	readOnly := false
	if request.Parameters["readOnly"] != nil {
		var ok bool
		readOnly, ok = request.Parameters["readOnly"].(bool)
		if !ok {
			return nil, fmt.Errorf("readOnly parameter must be a boolean")
		}
	}

	message, metadata, err := useCase.ExecuteTransaction(ctx, dbID, action, txID, statement, params, readOnly)
	if err != nil {
		return nil, err
	}

	// Create response with text and metadata
	resp := createTextResponse(message)

	// Add metadata if provided
	for k, v := range metadata {
		addMetadata(resp, k, v)
	}

	return resp, nil
}

//------------------------------------------------------------------------------
// PerformanceTool implementation
//------------------------------------------------------------------------------

// PerformanceTool handles query performance analysis
type PerformanceTool struct {
	BaseToolType
}

// NewPerformanceTool creates a new performance tool type
func NewPerformanceTool() *PerformanceTool {
	return &PerformanceTool{
		BaseToolType: BaseToolType{
			name:        "performance",
			description: "Analyze query performance",
		},
	}
}

// CreateTool creates a performance analysis tool
func (t *PerformanceTool) CreateTool(name string, dbID string) interface{} {
	return tools.NewTool(
		name,
		tools.WithDescription(t.GetDescription(dbID)),
		tools.WithString("action",
			tools.Description("Action (getSlowQueries, getMetrics, analyzeQuery, reset, setThreshold)"),
			tools.Required(),
		),
		tools.WithString("query",
			tools.Description("SQL query to analyze (required for analyzeQuery)"),
		),
		tools.WithNumber("limit",
			tools.Description("Maximum number of results to return"),
		),
		tools.WithNumber("threshold",
			tools.Description("Slow query threshold in milliseconds (required for setThreshold)"),
		),
	)
}

// HandleRequest handles performance tool requests
func (t *PerformanceTool) HandleRequest(ctx context.Context, request server.ToolCallRequest, dbID string, useCase UseCaseProvider) (interface{}, error) {
	// If dbID is not provided, extract it from the tool name
	if dbID == "" {
		dbID = extractDatabaseIDFromName(request.Name)
	}

	// This is a simplified implementation
	// In a real implementation, this would analyze query performance

	action, ok := request.Parameters["action"].(string)
	if !ok {
		return nil, fmt.Errorf("action parameter must be a string")
	}

	var limit int
	if request.Parameters["limit"] != nil {
		if limitParam, ok := request.Parameters["limit"].(float64); ok {
			limit = int(limitParam)
		}
	}

	query := ""
	if request.Parameters["query"] != nil {
		var ok bool
		query, ok = request.Parameters["query"].(string)
		if !ok {
			return nil, fmt.Errorf("query parameter must be a string")
		}
	}

	var threshold int
	if request.Parameters["threshold"] != nil {
		if thresholdParam, ok := request.Parameters["threshold"].(float64); ok {
			threshold = int(thresholdParam)
		}
	}

	// This is where we would call the useCase to analyze performance
	// For now, just return a placeholder
	output := fmt.Sprintf("Performance analysis for action '%s' on database '%s'\n", action, dbID)

	if query != "" {
		output += fmt.Sprintf("Query: %s\n", query)
	}

	if limit > 0 {
		output += fmt.Sprintf("Limit: %d\n", limit)
	}

	if threshold > 0 {
		output += fmt.Sprintf("Threshold: %d ms\n", threshold)
	}

	return createTextResponse(output), nil
}

//------------------------------------------------------------------------------
// SchemaTool implementation
//------------------------------------------------------------------------------

// SchemaTool handles database schema exploration
type SchemaTool struct {
	BaseToolType
}

// NewSchemaTool creates a new schema tool type
func NewSchemaTool() *SchemaTool {
	return &SchemaTool{
		BaseToolType: BaseToolType{
			name:        "schema",
			description: "Get schema of",
		},
	}
}

// CreateTool creates a schema tool
func (t *SchemaTool) CreateTool(name string, dbID string) interface{} {
	return tools.NewTool(
		name,
		tools.WithDescription(t.GetDescription(dbID)),
		// Use any string parameter for compatibility
		tools.WithString("random_string",
			tools.Description("Dummy parameter (optional)"),
		),
	)
}

// HandleRequest handles schema tool requests
func (t *SchemaTool) HandleRequest(ctx context.Context, request server.ToolCallRequest, dbID string, useCase UseCaseProvider) (interface{}, error) {
	// If dbID is not provided, extract it from the tool name
	if dbID == "" {
		dbID = extractDatabaseIDFromName(request.Name)
	}

	info, err := useCase.GetDatabaseInfo(dbID)
	if err != nil {
		return nil, err
	}

	// Format response text
	infoStr := fmt.Sprintf("Database Schema for %s:\n\n%+v", dbID, info)
	return createTextResponse(infoStr), nil
}

//------------------------------------------------------------------------------
// ListDatabasesTool implementation
//------------------------------------------------------------------------------

// ListDatabasesTool handles listing available databases
type ListDatabasesTool struct {
	BaseToolType
}

// NewListDatabasesTool creates a new list databases tool type
func NewListDatabasesTool() *ListDatabasesTool {
	return &ListDatabasesTool{
		BaseToolType: BaseToolType{
			name:        "list_databases",
			description: "List all available databases",
		},
	}
}

// CreateTool creates a list databases tool
func (t *ListDatabasesTool) CreateTool(name string, dbID string) interface{} {
	return tools.NewTool(
		name,
		tools.WithDescription(t.GetDescription(dbID)),
		// Use any string parameter for compatibility
		tools.WithString("random_string",
			tools.Description("Dummy parameter (optional)"),
		),
	)
}

// HandleRequest handles list databases tool requests
func (t *ListDatabasesTool) HandleRequest(ctx context.Context, request server.ToolCallRequest, dbID string, useCase UseCaseProvider) (interface{}, error) {
	databases := useCase.ListDatabases()

	// Format as text for display
	output := "Available databases:\n\n"
	for i, db := range databases {
		output += fmt.Sprintf("%d. %s\n", i+1, db)
	}

	if len(databases) == 0 {
		output += "No databases configured.\n"
	}

	return createTextResponse(output), nil
}

//------------------------------------------------------------------------------
// SurgeTool implementation
//------------------------------------------------------------------------------

// SurgeTool handles cryptocurrency surge detection and analysis
type SurgeTool struct {
	BaseToolType
}

// NewSurgeTool creates a new surge detection tool type
func NewSurgeTool() *SurgeTool {
	return &SurgeTool{
		BaseToolType: BaseToolType{
			name:        "detect_surging_cryptocurrencies",
			description: "Detect and analyze surging cryptocurrencies",
		},
	}
}

// CreateTool creates a surge detection tool
func (t *SurgeTool) CreateTool(name string, dbID string) interface{} {
	return tools.NewTool(
		name,
		tools.WithDescription(t.GetDescription(dbID)),
		tools.WithString("analysis_type",
			tools.Description("Type of surge analysis (gainers, volume_spike, anomalies, comprehensive)"),
			tools.Required(),
		),
		tools.WithNumber("timeframe_hours",
			tools.Description("Timeframe for analysis in hours (default: 1)"),
		),
		tools.WithNumber("result_limit",
			tools.Description("Maximum number of results to return (default: 10)"),
		),
		tools.WithNumber("sensitivity",
			tools.Description("Detection sensitivity level 1-5 (default: 3)"),
		),
		tools.WithNumber("min_change_rate",
			tools.Description("Minimum change rate percentage for surge detection (default: 5.0)"),
		),
	)
}

// HandleRequest handles surge detection tool requests
func (t *SurgeTool) HandleRequest(ctx context.Context, request server.ToolCallRequest, dbID string, useCase UseCaseProvider) (interface{}, error) {
	// If dbID is not provided, extract it from the tool name
	if dbID == "" {
		dbID = extractDatabaseIDFromName(request.Name)
	}

	analysisType, ok := request.Parameters["analysis_type"].(string)
	if !ok {
		return nil, fmt.Errorf("analysis_type parameter must be a string")
	}

	// Default parameters
	timeframeHours := 1
	resultLimit := 10
	sensitivity := 3
	minChangeRate := 5.0

	// Parse optional parameters
	if request.Parameters["timeframe_hours"] != nil {
		if hours, ok := request.Parameters["timeframe_hours"].(float64); ok {
			timeframeHours = int(hours)
		}
	}

	if request.Parameters["result_limit"] != nil {
		if limit, ok := request.Parameters["result_limit"].(float64); ok {
			resultLimit = int(limit)
		}
	}

	if request.Parameters["sensitivity"] != nil {
		if sens, ok := request.Parameters["sensitivity"].(float64); ok {
			sensitivity = int(sens)
		}
	}

	if request.Parameters["min_change_rate"] != nil {
		if rate, ok := request.Parameters["min_change_rate"].(float64); ok {
			minChangeRate = rate
		}
	}

	var result string
	var err error

	switch analysisType {
	case "gainers":
		result, err = t.analyzeGainers(ctx, useCase, dbID, timeframeHours, resultLimit, minChangeRate)
	case "volume_spike":
		result, err = t.analyzeVolumeSpikes(ctx, useCase, dbID, timeframeHours, resultLimit, sensitivity)
	case "anomalies":
		result, err = t.analyzeAnomalies(ctx, useCase, dbID, timeframeHours, sensitivity)
	case "comprehensive":
		result, err = t.comprehensiveAnalysis(ctx, useCase, dbID, timeframeHours, resultLimit, sensitivity, minChangeRate)
	default:
		return nil, fmt.Errorf("unsupported analysis_type: %s. Supported types: gainers, volume_spike, anomalies, comprehensive", analysisType)
	}

	if err != nil {
		return nil, err
	}

	return createTextResponse(result), nil
}

// analyzeGainers focuses on price surge detection
func (t *SurgeTool) analyzeGainers(ctx context.Context, useCase UseCaseProvider, dbID string, timeframeHours, resultLimit int, minChangeRate float64) (string, error) {
	query := fmt.Sprintf(`
		SELECT code, price, change_rate, volume_change, momentum, market_sentiment
		FROM get_market_movers('gainers', %d, %d)
		WHERE change_rate >= %f
		ORDER BY change_rate DESC;
	`, resultLimit, timeframeHours, minChangeRate)

	result, err := useCase.ExecuteQuery(ctx, dbID, query, nil)
	if err != nil {
		return "", fmt.Errorf("failed to analyze gainers: %w", err)
	}

	return fmt.Sprintf("🚀 SURGE ANALYSIS - Price Gainers (≥%.1f%% in %dh):\n\n%s", minChangeRate, timeframeHours, result), nil
}

// analyzeVolumeSpikes focuses on volume-based surge detection
func (t *SurgeTool) analyzeVolumeSpikes(ctx context.Context, useCase UseCaseProvider, dbID string, timeframeHours, resultLimit, sensitivity int) (string, error) {
	query := fmt.Sprintf(`
		SELECT code, price, change_rate, volume_change, momentum
		FROM get_market_movers('volume', %d, %d)
		WHERE volume_change > 150.0
		ORDER BY volume_change DESC;
	`, resultLimit, timeframeHours)

	result, err := useCase.ExecuteQuery(ctx, dbID, query, nil)
	if err != nil {
		return "", fmt.Errorf("failed to analyze volume spikes: %w", err)
	}

	return fmt.Sprintf("📊 SURGE ANALYSIS - Volume Spikes (>150%% increase in %dh):\n\n%s", timeframeHours, result), nil
}

// analyzeAnomalies focuses on anomaly-based surge detection
func (t *SurgeTool) analyzeAnomalies(ctx context.Context, useCase UseCaseProvider, dbID string, timeframeHours, sensitivity int) (string, error) {
	query := fmt.Sprintf(`
		SELECT anomaly_type, code, severity, spike_ratio, price_change, description
		FROM detect_anomalies(%d, %d)
		WHERE severity IN ('critical', 'high')
		ORDER BY 
			CASE severity 
				WHEN 'critical' THEN 1
				WHEN 'high' THEN 2
				ELSE 3
			END,
			spike_ratio DESC, price_change DESC;
	`, timeframeHours, sensitivity)

	result, err := useCase.ExecuteQuery(ctx, dbID, query, nil)
	if err != nil {
		return "", fmt.Errorf("failed to analyze anomalies: %w", err)
	}

	return fmt.Sprintf("⚡ SURGE ANALYSIS - Market Anomalies (Critical & High severity in %dh):\n\n%s", timeframeHours, result), nil
}

// comprehensiveAnalysis combines multiple detection methods
func (t *SurgeTool) comprehensiveAnalysis(ctx context.Context, useCase UseCaseProvider, dbID string, timeframeHours, resultLimit, sensitivity int, minChangeRate float64) (string, error) {
	var result strings.Builder

	// 1. Market Overview
	overviewQuery := "SELECT * FROM get_market_overview();"
	overview, err := useCase.ExecuteQuery(ctx, dbID, overviewQuery, nil)
	if err != nil {
		return "", fmt.Errorf("failed to get market overview: %w", err)
	}
	result.WriteString(fmt.Sprintf("📈 COMPREHENSIVE SURGE ANALYSIS (%dh timeframe)\n\n", timeframeHours))
	result.WriteString("=== MARKET OVERVIEW ===\n")
	result.WriteString(overview)
	result.WriteString("\n\n")

	// 2. Top Gainers
	gainersQuery := fmt.Sprintf(`
		SELECT code, price, change_rate, momentum, market_sentiment
		FROM get_market_movers('gainers', %d, %d)
		WHERE change_rate >= %f
		ORDER BY change_rate DESC LIMIT 5;
	`, resultLimit, timeframeHours, minChangeRate)

	gainers, err := useCase.ExecuteQuery(ctx, dbID, gainersQuery, nil)
	if err != nil {
		return "", fmt.Errorf("failed to get top gainers: %w", err)
	}
	result.WriteString("=== TOP SURGING COINS (Price) ===\n")
	result.WriteString(gainers)
	result.WriteString("\n\n")

	// 3. Volume Anomalies
	volumeQuery := fmt.Sprintf(`
		SELECT code, severity, spike_ratio, description
		FROM detect_anomalies(%d, %d)
		WHERE anomaly_type = 'volume_spike' 
		  AND severity IN ('critical', 'high')
		ORDER BY spike_ratio DESC LIMIT 5;
	`, timeframeHours, sensitivity)

	volumeAnomalies, err := useCase.ExecuteQuery(ctx, dbID, volumeQuery, nil)
	if err != nil {
		return "", fmt.Errorf("failed to get volume anomalies: %w", err)
	}
	result.WriteString("=== VOLUME SURGE ALERTS ===\n")
	result.WriteString(volumeAnomalies)
	result.WriteString("\n\n")

	// 4. Price Volatility Alerts
	priceQuery := fmt.Sprintf(`
		SELECT code, severity, price_change, description
		FROM detect_anomalies(%d, %d)
		WHERE anomaly_type = 'price_volatility'
		  AND severity IN ('critical', 'high')
		ORDER BY price_change DESC LIMIT 5;
	`, timeframeHours, sensitivity)

	priceAnomalies, err := useCase.ExecuteQuery(ctx, dbID, priceQuery, nil)
	if err != nil {
		return "", fmt.Errorf("failed to get price anomalies: %w", err)
	}
	result.WriteString("=== PRICE VOLATILITY ALERTS ===\n")
	result.WriteString(priceAnomalies)
	result.WriteString("\n")

	return result.String(), nil
}

//------------------------------------------------------------------------------
// ToolTypeFactory provides a factory for creating tool types
//------------------------------------------------------------------------------

// ToolTypeFactory creates and manages tool types
type ToolTypeFactory struct {
	toolTypes map[string]ToolType
}

// NewToolTypeFactory creates a new tool type factory with all registered tool types
func NewToolTypeFactory() *ToolTypeFactory {
	factory := &ToolTypeFactory{
		toolTypes: make(map[string]ToolType),
	}

	// Register all tool types
	factory.Register(NewQueryTool())
	factory.Register(NewExecuteTool())
	factory.Register(NewTransactionTool())
	factory.Register(NewPerformanceTool())
	factory.Register(NewSchemaTool())
	factory.Register(NewListDatabasesTool())
	factory.Register(NewSurgeTool()) // Register the new surge detection tool

	return factory
}

// Register adds a tool type to the factory
func (f *ToolTypeFactory) Register(toolType ToolType) {
	f.toolTypes[toolType.GetName()] = toolType
}

// GetToolType returns a tool type by name
func (f *ToolTypeFactory) GetToolType(name string) (ToolType, bool) {
	// Handle new simpler format: <tooltype>_<dbID> or just the tool type name
	parts := strings.Split(name, "_")
	if len(parts) > 0 {
		// First part is the tool type name
		toolType, ok := f.toolTypes[parts[0]]
		if ok {
			return toolType, true
		}
	}

	// Direct tool type lookup
	toolType, ok := f.toolTypes[name]
	return toolType, ok
}

// GetToolTypeForSourceName finds the appropriate tool type for a source name
func (f *ToolTypeFactory) GetToolTypeForSourceName(sourceName string) (ToolType, string, bool) {
	// Handle simpler format: <tooltype>_<dbID>
	parts := strings.Split(sourceName, "_")

	if len(parts) >= 2 {
		// First part is tool type, last part is dbID
		toolTypeName := parts[0]
		dbID := parts[len(parts)-1]

		toolType, ok := f.toolTypes[toolTypeName]
		if ok {
			return toolType, dbID, true
		}
	}

	// Handle case for global tools
	if sourceName == "list_databases" {
		toolType, ok := f.toolTypes["list_databases"]
		return toolType, "", ok
	}

	return nil, "", false
}

// GetAllToolTypes returns all registered tool types
func (f *ToolTypeFactory) GetAllToolTypes() []ToolType {
	types := make([]ToolType, 0, len(f.toolTypes))
	for _, toolType := range f.toolTypes {
		types = append(types, toolType)
	}
	return types
}
