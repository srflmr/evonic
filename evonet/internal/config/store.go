package config

import (
	"os"

	"gopkg.in/yaml.v3"
)

// Store holds multiple paired servers and tracks the active one.
//
// It is layered on top of the single-server Config: the GUI manages the Store
// (servers.yaml), while the CLI keeps reading the active server from config.yaml.
// SaveStore syncs config.yaml to the active server; LoadStore reconciles any
// server paired via the CLI back into the Store.
type Store struct {
	Active  string    `yaml:"active"` // HomeID (or ServerURL) of the active server
	Servers []*Config `yaml:"servers"`
}

// storePath returns the path to servers.yaml in the platform config dir.
func storePath() (string, error) {
	dir, err := configDir()
	if err != nil {
		return "", err
	}
	return dir + "/servers.yaml", nil
}

// serverKey returns the identity key for a server: HomeID, or ServerURL if unset.
func serverKey(c *Config) string {
	if c.HomeID != "" {
		return c.HomeID
	}
	return c.ServerURL
}

// LoadStore reads servers.yaml. If it does not exist, it migrates the existing
// single-server config (embedded + config.yaml) into a new Store. It also
// reconciles any server present in config.yaml that is missing from the Store
// (e.g. paired via the CLI after the Store was created).
func LoadStore() (*Store, error) {
	s := &Store{}

	path, err := storePath()
	if err == nil {
		if data, rerr := os.ReadFile(path); rerr == nil {
			_ = yaml.Unmarshal(data, s)
		}
	}

	// Migration: empty store but a single config exists → seed from it.
	single, _ := Load("")
	if len(s.Servers) == 0 {
		if single != nil && single.ConnectorToken != "" && single.ServerURL != "" {
			s.Servers = []*Config{single}
			s.Active = serverKey(single)
		}
		return s, nil
	}

	// Reconcile: import a CLI-paired server that isn't in the store yet.
	if single != nil && single.ConnectorToken != "" && single.ServerURL != "" {
		key := serverKey(single)
		found := false
		for _, srv := range s.Servers {
			if serverKey(srv) == key {
				found = true
				break
			}
		}
		if !found {
			s.Servers = append(s.Servers, single)
		}
	}

	return s, nil
}

// SaveStore writes servers.yaml and syncs config.yaml to the active server so
// the CLI (start/run/status) follows the GUI's selection.
func SaveStore(s *Store) error {
	path, err := storePath()
	if err != nil {
		return err
	}
	dir, err := configDir()
	if err != nil {
		return err
	}
	if err := os.MkdirAll(dir, 0700); err != nil {
		return err
	}
	data, err := yaml.Marshal(s)
	if err != nil {
		return err
	}
	if err := os.WriteFile(path, data, 0600); err != nil {
		return err
	}
	// Keep config.yaml in sync with the active server (best effort).
	if active := s.ActiveConfig(); active.ConnectorToken != "" {
		_ = Save(active)
	}
	return nil
}

// ActiveConfig returns the active server, falling back to the first server,
// then to an empty Config.
func (s *Store) ActiveConfig() *Config {
	for _, srv := range s.Servers {
		if serverKey(srv) == s.Active {
			return srv
		}
	}
	if len(s.Servers) > 0 {
		return s.Servers[0]
	}
	return &Config{}
}

// SetActive marks the server with the given key (HomeID or ServerURL) as active.
func (s *Store) SetActive(key string) {
	s.Active = key
}

// Upsert replaces a server matching by key, otherwise appends it.
func (s *Store) Upsert(cfg *Config) {
	key := serverKey(cfg)
	for i, srv := range s.Servers {
		if serverKey(srv) == key {
			s.Servers[i] = cfg
			return
		}
	}
	s.Servers = append(s.Servers, cfg)
}

// Remove deletes the server matching the given key. If it was active, the
// active server falls back to the first remaining server (or empty).
func (s *Store) Remove(key string) {
	out := s.Servers[:0]
	for _, srv := range s.Servers {
		if serverKey(srv) != key {
			out = append(out, srv)
		}
	}
	s.Servers = out
	if s.Active == key {
		if len(s.Servers) > 0 {
			s.Active = serverKey(s.Servers[0])
		} else {
			s.Active = ""
		}
	}
}
