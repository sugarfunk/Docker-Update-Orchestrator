import React, { useState, useEffect } from 'react';
import axios from 'axios';

const API_URL = process.env.REACT_APP_API_URL || 'http://localhost:8000';

function Updates() {
  const [updates, setUpdates] = useState([]);
  const [loading, setLoading] = useState(true);
  const [filter, setFilter] = useState('pending');

  useEffect(() => {
    fetchUpdates();
  }, [filter]);

  const fetchUpdates = async () => {
    try {
      let url = `${API_URL}/api/v1/updates/`;
      if (filter !== 'all') {
        url += `?status=${filter}`;
      }

      const response = await axios.get(url);
      setUpdates(response.data);
      setLoading(false);
    } catch (err) {
      console.error('Failed to fetch updates:', err);
      setLoading(false);
    }
  };

  const handleApprove = async (updateId) => {
    try {
      await axios.post(`${API_URL}/api/v1/updates/${updateId}/approve`, {
        approved: true
      });
      fetchUpdates(); // Refresh list
    } catch (err) {
      console.error('Failed to approve update:', err);
    }
  };

  const handleExecute = async (updateId) => {
    try {
      await axios.post(`${API_URL}/api/v1/updates/${updateId}/execute`);
      fetchUpdates(); // Refresh list
    } catch (err) {
      console.error('Failed to execute update:', err);
    }
  };

  if (loading) {
    return <div className="loading">Loading updates...</div>;
  }

  return (
    <div className="updates">
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '2rem' }}>
        <h1>Updates</h1>
        <select
          className="btn btn-secondary"
          value={filter}
          onChange={(e) => setFilter(e.target.value)}
        >
          <option value="all">All Updates</option>
          <option value="pending">Pending</option>
          <option value="approved">Approved</option>
          <option value="in_progress">In Progress</option>
          <option value="completed">Completed</option>
          <option value="failed">Failed</option>
        </select>
      </div>

      <div className="card">
        <table className="table">
          <thead>
            <tr>
              <th>Container</th>
              <th>Server</th>
              <th>Version Change</th>
              <th>Type</th>
              <th>Risk</th>
              <th>Breaking Changes</th>
              <th>Status</th>
              <th>Actions</th>
            </tr>
          </thead>
          <tbody>
            {updates.map(update => (
              <tr key={update.id}>
                <td>{update.container_name}</td>
                <td>{update.server_name}</td>
                <td>
                  {update.from_version} → {update.to_version}
                </td>
                <td>
                  <span className={`badge ${
                    update.update_type === 'major' ? 'badge-danger' :
                    update.update_type === 'minor' ? 'badge-warning' :
                    update.update_type === 'security' ? 'badge-danger' :
                    'badge-info'
                  }`}>
                    {update.update_type}
                  </span>
                </td>
                <td>
                  <span className={`badge ${
                    update.risk_level === 'critical' || update.risk_level === 'high' ? 'badge-danger' :
                    update.risk_level === 'medium' ? 'badge-warning' :
                    'badge-success'
                  }`}>
                    {update.risk_level || 'unknown'}
                  </span>
                </td>
                <td>
                  {update.has_breaking_changes ? (
                    <span className="badge badge-danger">Yes</span>
                  ) : (
                    <span className="badge badge-success">No</span>
                  )}
                </td>
                <td>
                  <span className={`badge ${
                    update.status === 'completed' ? 'badge-success' :
                    update.status === 'failed' ? 'badge-danger' :
                    update.status === 'in_progress' ? 'badge-info' :
                    'badge-warning'
                  }`}>
                    {update.status}
                  </span>
                </td>
                <td>
                  <div style={{ display: 'flex', gap: '0.5rem' }}>
                    {update.status === 'pending' && (
                      <>
                        <button
                          className="btn btn-primary"
                          onClick={() => handleApprove(update.id)}
                        >
                          Approve
                        </button>
                        <button className="btn btn-secondary">Details</button>
                      </>
                    )}
                    {update.status === 'approved' && (
                      <button
                        className="btn btn-primary"
                        onClick={() => handleExecute(update.id)}
                      >
                        Execute
                      </button>
                    )}
                    {(update.status === 'completed' || update.status === 'failed') && (
                      <button className="btn btn-secondary">View Logs</button>
                    )}
                  </div>
                </td>
              </tr>
            ))}
          </tbody>
        </table>

        {updates.length === 0 && (
          <div style={{ textAlign: 'center', padding: '2rem', color: '#8b949e' }}>
            No updates found.
          </div>
        )}
      </div>
    </div>
  );
}

export default Updates;
