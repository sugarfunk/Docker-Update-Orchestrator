import React, { useState, useEffect } from 'react';
import axios from 'axios';

const API_URL = process.env.REACT_APP_API_URL || 'http://localhost:8000';

function Dashboard() {
  const [stats, setStats] = useState({
    containers: { total: 0, running: 0, updates_available: 0, critical: 0 },
    updates: { pending: 0, in_progress: 0, completed: 0, failed: 0 }
  });
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  useEffect(() => {
    fetchStats();
  }, []);

  const fetchStats = async () => {
    try {
      const [containersRes, updatesRes] = await Promise.all([
        axios.get(`${API_URL}/api/v1/containers/stats/summary`),
        axios.get(`${API_URL}/api/v1/updates/stats/summary`)
      ]);

      setStats({
        containers: containersRes.data,
        updates: updatesRes.data
      });
      setLoading(false);
    } catch (err) {
      setError('Failed to fetch statistics');
      setLoading(false);
    }
  };

  if (loading) {
    return <div className="loading">Loading dashboard...</div>;
  }

  if (error) {
    return <div className="error">{error}</div>;
  }

  return (
    <div className="dashboard">
      <h1>Dashboard</h1>

      <div className="stats-grid">
        <div className="stat-card">
          <div className="stat-value">{stats.containers.total_containers || 0}</div>
          <div className="stat-label">Total Containers</div>
        </div>

        <div className="stat-card">
          <div className="stat-value" style={{ color: '#3fb950' }}>
            {stats.containers.running_containers || 0}
          </div>
          <div className="stat-label">Running</div>
        </div>

        <div className="stat-card">
          <div className="stat-value" style={{ color: '#f85149' }}>
            {stats.containers.updates_available || 0}
          </div>
          <div className="stat-label">Updates Available</div>
        </div>

        <div className="stat-card">
          <div className="stat-value" style={{ color: '#d29922' }}>
            {stats.containers.critical_services || 0}
          </div>
          <div className="stat-label">Critical Services</div>
        </div>
      </div>

      <div className="card">
        <h2 className="card-title">Update Status</h2>
        <div className="stats-grid">
          <div className="stat-card">
            <div className="stat-value">{stats.updates.pending || 0}</div>
            <div className="stat-label">Pending</div>
          </div>

          <div className="stat-card">
            <div className="stat-value" style={{ color: '#58a6ff' }}>
              {stats.updates.in_progress || 0}
            </div>
            <div className="stat-label">In Progress</div>
          </div>

          <div className="stat-card">
            <div className="stat-value" style={{ color: '#3fb950' }}>
              {stats.updates.completed || 0}
            </div>
            <div className="stat-label">Completed</div>
          </div>

          <div className="stat-card">
            <div className="stat-value" style={{ color: '#f85149' }}>
              {stats.updates.failed || 0}
            </div>
            <div className="stat-label">Failed</div>
          </div>
        </div>
      </div>

      <div className="card">
        <h2 className="card-title">Quick Actions</h2>
        <div style={{ display: 'flex', gap: '1rem' }}>
          <button className="btn btn-primary">Scan All Servers</button>
          <button className="btn btn-secondary">Check for Updates</button>
          <button className="btn btn-secondary">View Pending Approvals</button>
        </div>
      </div>
    </div>
  );
}

export default Dashboard;
