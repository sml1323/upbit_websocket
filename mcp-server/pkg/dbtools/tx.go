package dbtools

import (
	"database/sql"
	"sync"
)

// Map to store active transactions
var transactions = make(map[string]*sql.Tx)
var transactionMutex sync.RWMutex

// StoreTransaction stores a transaction in the global map
func StoreTransaction(id string, tx *sql.Tx) {
	transactionMutex.Lock()
	defer transactionMutex.Unlock()
	transactions[id] = tx
}

// GetTransaction retrieves a transaction from the global map
func GetTransaction(id string) (*sql.Tx, bool) {
	transactionMutex.RLock()
	defer transactionMutex.RUnlock()
	tx, ok := transactions[id]
	return tx, ok
}

// RemoveTransaction removes a transaction from the global map
func RemoveTransaction(id string) {
	transactionMutex.Lock()
	defer transactionMutex.Unlock()
	delete(transactions, id)
}
