import React, { useState, useEffect } from 'react';
import axios from 'axios';

const API_URL = process.env.REACT_APP_API_URL || 'http://localhost:8000';

function Servers() {
  const [servers, setServers] = useState([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    fetchServers();
  }, []);

  const fetchServers = async () => {
    try {
      const response = await axios.get(`${API_URL}/api/v1/servers/`);
      setServers(response.data);
      setLoading(false);
    } catch (err) {
      console.error('Failed to fetch servers:', err);
      setLoading(false);
    }
  };

  const handleConnect = async (serverId) => {
    try {
      await axios.post(`${API_URL}/api/v1/servers/${serverId}/connect`);
      fetchServers(); // Refresh list
    } catch (err) {
      console.error('Failed to connect:', err);
    }
  };

  if (loading) {
    return <div className="loading">Loading servers...</div>;
  }

  return (
    <div className="servers">
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '2rem' }}>
        <h1>Servers</h1>
        <button className="btn btn-primary">Add Server</button>
      </div>

      <div className="card">
        <table className="table">
          <thead>
            <tr>
              <th>Name</th>
              <th>Hostname</th>
              <th>Status</th>
              <th>Docker Version</th>
              <th>Containers</th>
              <th>Actions</th>
            </tr>
          </thead>
          <tbody>
            {servers.map(server => (
              <tr key={server.id}>
                <td>{server.name}</td>
                <td>{server.hostname}</td>
                <td>
                  <span className={`badge ${
                    server.connection_status === 'connected' ? 'badge-success' :
                    server.connection_status === 'error' ? 'badge-danger' :
                    'badge-warning'
                  }`}>
                    {server.connection_status}
                  </span>
                </td>
                <td>{server.docker_version || 'N/A'}</td>
                <td>{server.containers_count}</td>
                <td>
                  <button
                    className="btn btn-secondary"
                    onClick={() => handleConnect(server.id)}
                  >
                    Connect
                  </button>
                </td>
              </tr>
            ))}
          </tbody>
        </table>

        {servers.length === 0 && (
          <div style={{ textAlign: 'center', padding: '2rem', color: '#8b949e' }}>
            No servers configured. Add a server to get started.
          </div>
        )}
      </div>
    </div>
  );
}

export default Servers;
