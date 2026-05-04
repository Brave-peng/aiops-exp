package main

import (
	"encoding/json"
	"log"
	"math"
	"net/http"
	"os"
	"strconv"
	"time"
)

type response struct {
	Service   string            `json:"service"`
	Hostname  string            `json:"hostname"`
	Timestamp string            `json:"timestamp"`
	Message   string            `json:"message,omitempty"`
	Env       map[string]string `json:"env,omitempty"`
}

func main() {
	port := getenv("PORT", "8080")
	serviceName := getenv("SERVICE_NAME", "demo-service")

	mux := http.NewServeMux()

	mux.HandleFunc("/", func(w http.ResponseWriter, r *http.Request) {
		writeJSON(w, http.StatusOK, baseResponse(serviceName, "ok"))
	})

	mux.HandleFunc("/healthz", func(w http.ResponseWriter, r *http.Request) {
		writeJSON(w, http.StatusOK, baseResponse(serviceName, "healthy"))
	})

	mux.HandleFunc("/readyz", func(w http.ResponseWriter, r *http.Request) {
		writeJSON(w, http.StatusOK, baseResponse(serviceName, "ready"))
	})

	mux.HandleFunc("/config", func(w http.ResponseWriter, r *http.Request) {
		resp := baseResponse(serviceName, "config")
		resp.Env = map[string]string{
			"SERVICE_NAME":    serviceName,
			"DOWNSTREAM_URL": getenv("DOWNSTREAM_URL", ""),
			"PORT":           port,
		}
		writeJSON(w, http.StatusOK, resp)
	})

	mux.HandleFunc("/work", func(w http.ResponseWriter, r *http.Request) {
		ms := intQuery(r, "ms", 100)
		until := time.Now().Add(time.Duration(ms) * time.Millisecond)
		x := 0.0001
		for time.Now().Before(until) {
			x += math.Sqrt(x)
		}

		resp := baseResponse(serviceName, "work complete")
		resp.Env = map[string]string{"duration_ms": strconv.Itoa(ms)}
		writeJSON(w, http.StatusOK, resp)
	})

	addr := ":" + port
	log.Printf("starting %s on %s", serviceName, addr)
	if err := http.ListenAndServe(addr, mux); err != nil {
		log.Fatal(err)
	}
}

func baseResponse(serviceName, msg string) response {
	hostname, _ := os.Hostname()
	return response{
		Service:   serviceName,
		Hostname:  hostname,
		Timestamp: time.Now().UTC().Format(time.RFC3339Nano),
		Message:   msg,
	}
}

func writeJSON(w http.ResponseWriter, status int, v any) {
	w.Header().Set("Content-Type", "application/json")
	w.WriteHeader(status)
	_ = json.NewEncoder(w).Encode(v)
}

func getenv(key, fallback string) string {
	if val := os.Getenv(key); val != "" {
		return val
	}
	return fallback
}

func intQuery(r *http.Request, key string, fallback int) int {
	raw := r.URL.Query().Get(key)
	if raw == "" {
		return fallback
	}
	val, err := strconv.Atoi(raw)
	if err != nil || val < 0 {
		return fallback
	}
	if val > 30000 {
		return 30000
	}
	return val
}

