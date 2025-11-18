import React, { useState, useEffect } from 'react';
import axios from 'axios';

const API_URL = process.env.REACT_APP_API_URL || 'http://localhost:8000';

function Containers() {
  const [containers, setContainers] = useState([]);
  const [loading, setLoading] = useState(true);
  const [filter, setFilter] = useState('all');

  useEffect(() => {
    fetchContainers();
  }, [filter]);

  const fetchContainers = async () => {
    try {
      let url = `${API_URL}/api/v1/containers/`;
      if (filter === 'updates') {
        url += '?update_available=true';
      } else if (filter === 'critical') {
        url += '?is_critical=true';
      }

      const response = await axios.get(url);
      setContainers(response.data);
      setLoading(false);
    } catch (err) {
      console.error('Failed to fetch containers:', err);
      setLoading(false);
    }
  };

  if (loading) {
    return <div className="loading">Loading containers...</div>;
  }

  return (
    <div className="containers">
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '2rem' }}>
        <h1>Containers</h1>
        <div style={{ display: 'flex', gap: '1rem' }}>
          <select
            className="btn btn-secondary"
            value={filter}
            onChange={(e) => setFilter(e.target.value)}
          >
            <option value="all">All Containers</option>
            <option value="updates">Updates Available</option>
            <option value="critical">Critical Services</option>
          </select>
          <button className="btn btn-primary">Scan Containers</button>
        </div>
      </div>

      <div className="card">
        <table className="table">
          <thead>
            <tr>
              <th>Container</th>
              <th>Server</th>
              <th>Image</th>
              <th>Current Version</th>
              <th>Status</th>
              <th>Updates</th>
              <th>Actions</th>
            </tr>
          </thead>
          <tbody>
            {containers.map(container => (
              <tr key={container.id}>
                <td>
                  {container.container_name}
                  {container.is_critical && (
                    <span className="badge badge-danger" style={{ marginLeft: '0.5rem' }}>
                      Critical
                    </span>
                  )}
                </td>
                <td>{container.server_name}</td>
                <td>{container.image}</td>
                <td>{container.tag}</td>
                <td>
                  <span className={`badge ${
                    container.is_running ? 'badge-success' : 'badge-danger'
                  }`}>
                    {container.status}
                  </span>
                </td>
                <td>
                  {container.update_available ? (
                    <span className="badge badge-warning">
                      {container.latest_version} available
                    </span>
                  ) : (
                    <span className="badge badge-success">Up to date</span>
                  )}
                </td>
                <td>
                  <button className="btn btn-secondary">Details</button>
                </td>
              </tr>
            ))}
          </tbody>
        </table>

        {containers.length === 0 && (
          <div style={{ textAlign: 'center', padding: '2rem', color: '#8b949e' }}>
            No containers found. Scan your servers to discover containers.
          </div>
        )}
      </div>
    </div>
  );
}

export default Containers;
