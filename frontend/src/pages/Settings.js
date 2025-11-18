import React from 'react';

function Settings() {
  return (
    <div className="settings">
      <h1>Settings</h1>

      <div className="card">
        <h2 className="card-title">Global Configuration</h2>
        <form>
          <div style={{ marginBottom: '1rem' }}>
            <label>Update Check Interval (hours)</label>
            <input type="number" className="btn btn-secondary" defaultValue="6" />
          </div>

          <div style={{ marginBottom: '1rem' }}>
            <label>Max Concurrent Updates</label>
            <input type="number" className="btn btn-secondary" defaultValue="3" />
          </div>

          <div style={{ marginBottom: '1rem' }}>
            <label>
              <input type="checkbox" defaultChecked /> Enable Auto-Rollback
            </label>
          </div>

          <div style={{ marginBottom: '1rem' }}>
            <label>
              <input type="checkbox" defaultChecked /> Backup Before Update
            </label>
          </div>
        </form>
      </div>

      <div className="card">
        <h2 className="card-title">LLM Configuration</h2>
        <form>
          <div style={{ marginBottom: '1rem' }}>
            <label>Primary LLM Provider</label>
            <select className="btn btn-secondary">
              <option>Anthropic (Claude)</option>
              <option>OpenAI (GPT)</option>
              <option>Google (Gemini)</option>
              <option>Ollama (Local)</option>
            </select>
          </div>

          <div style={{ marginBottom: '1rem' }}>
            <label>API Key</label>
            <input type="password" className="btn btn-secondary" placeholder="sk-..." />
          </div>

          <div style={{ marginBottom: '1rem' }}>
            <label>
              <input type="checkbox" /> Use Local LLM for Sensitive Data
            </label>
          </div>
        </form>
      </div>

      <div className="card">
        <h2 className="card-title">Notification Settings</h2>
        <form>
          <div style={{ marginBottom: '1rem' }}>
            <label>
              <input type="checkbox" defaultChecked /> Enable NTFY Notifications
            </label>
          </div>

          <div style={{ marginBottom: '1rem' }}>
            <label>NTFY Topic</label>
            <input type="text" className="btn btn-secondary" defaultValue="docker-updates" />
          </div>

          <div style={{ marginBottom: '1rem' }}>
            <label>
              <input type="checkbox" /> Enable Email Notifications
            </label>
          </div>

          <div style={{ marginBottom: '1rem' }}>
            <label>Email Recipients (comma-separated)</label>
            <input type="text" className="btn btn-secondary" placeholder="admin@example.com" />
          </div>
        </form>
      </div>

      <div style={{ marginTop: '2rem' }}>
        <button className="btn btn-primary">Save Settings</button>
      </div>
    </div>
  );
}

export default Settings;
