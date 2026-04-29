import React, { useState, useEffect } from 'react';
import { BrowserRouter as Router, Routes, Route, Navigate } from 'react-router-dom';
import MenuItemForm from './components/Menu/MenuItemForm';
import ManageMenuItems from './components/Menu/ManageMenuItems';
import RestaurantPage from './components/Restaurant/RestaurantPage';
import RestaurantList from './components/Restaurant/RestaurantList';
import LandingPage from './components/General/LandingPage';
import RegisterRestaurant from './components/Restaurant/RegisterRestaurant';
import ProfilePage from './components/General/ProfilePage';
import AdminPanel from './components/General/AdminPanel';
import Header from './components/General/Header';
import DashboardPage from './components/General/DashboardPage';

// Simplified Protected Route - uses localStorage directly for quick checks
const ProtectedRoute = ({ element }) => {
  const token = localStorage.getItem('auth_token');
  
  if (!token) {
    // Redirect to login if not authenticated
    return <Navigate to="/" replace />;
  }
  
  return element;
};

// Simplified Admin Route - uses localStorage directly for quick checks
const AdminRoute = ({ element }) => {
  const token = localStorage.getItem('auth_token');
  const isAdmin = localStorage.getItem('is_admin') === 'true';
  
  if (!token) {
    // Redirect to login if not authenticated
    return <Navigate to="/" replace />;
  }
  
  if (!isAdmin) {
    return <Navigate to="/dashboard" replace />;
  }
  
  return element;
};

function App() {
  const [restaurantId, setRestaurantId] = useState(localStorage.getItem('restaurant_id') || null);
  
  // Listen for auth changes to update restaurantId
  useEffect(() => {
    const updateRestaurantId = () => {
      setRestaurantId(localStorage.getItem('restaurant_id') || null);
    };
    
    window.addEventListener('auth-change', updateRestaurantId);
    
    return () => {
      window.removeEventListener('auth-change', updateRestaurantId);
    };
  }, []);

  return (
    <Router>
      <div className="min-h-screen bg-gray-50">
        {/* Header - passing current restaurantId */}
        <Header restaurantId={restaurantId} />
        
        <main className="py-6">
          <Routes>
            {/* Public routes */}
            <Route path="/" element={<LandingPage />} />
            <Route path="/signup" element={<RegisterRestaurant />} />
            
            {/* Protected routes */}
            <Route 
              path="/dashboard" 
              element={<ProtectedRoute element={<DashboardPage />} />} 
            />
            <Route 
              path="/profile" 
              element={<ProtectedRoute element={<ProfilePage />} />} 
            />
            <Route 
              path="/restaurant/:restaurantId" 
              element={<ProtectedRoute element={<RestaurantPage />} />} 
            />
            <Route 
              path="/restaurant/:restaurantId/menu" 
              element={<ProtectedRoute element={<ManageMenuItems />} />} 
            />
            <Route 
              path="/add-restaurant" 
              element={<ProtectedRoute element={<RegisterRestaurant />} />} 
            />
            
            {/* Admin-only routes */}
            <Route 
              path="/restaurant-list" 
              element={<AdminRoute element={<RestaurantList />} />} 
            />
            <Route 
              path="/admin" 
              element={<AdminRoute element={<AdminPanel />} />} 
            />

            {/* Fallback route */}
            <Route path="*" element={<Navigate to="/" replace />} />
          </Routes>
        </main>
      </div>
    </Router>
  );
}

export default App;