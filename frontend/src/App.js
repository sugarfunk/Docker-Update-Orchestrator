import React from 'react';
import { BrowserRouter as Router, Routes, Route, Link } from 'react-router-dom';
import './App.css';
import Dashboard from './pages/Dashboard';
import Servers from './pages/Servers';
import Containers from './pages/Containers';
import Updates from './pages/Updates';
import Settings from './pages/Settings';

function App() {
  return (
    <Router>
      <div className="App">
        <nav className="navbar">
          <div className="nav-container">
            <h1 className="nav-title">🐳 Docker Update Orchestrator</h1>
            <ul className="nav-menu">
              <li><Link to="/">Dashboard</Link></li>
              <li><Link to="/servers">Servers</Link></li>
              <li><Link to="/containers">Containers</Link></li>
              <li><Link to="/updates">Updates</Link></li>
              <li><Link to="/settings">Settings</Link></li>
            </ul>
          </div>
        </nav>

        <main className="main-content">
          <Routes>
            <Route path="/" element={<Dashboard />} />
            <Route path="/servers" element={<Servers />} />
            <Route path="/containers" element={<Containers />} />
            <Route path="/updates" element={<Updates />} />
            <Route path="/settings" element={<Settings />} />
          </Routes>
        </main>
      </div>
    </Router>
  );
}

export default App;
