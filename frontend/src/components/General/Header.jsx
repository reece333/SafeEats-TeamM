import React, { useState, useEffect } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import ProfileMenu from './ProfileMenu';
import { api } from '../../services/api';

const Header = ({ restaurantId }) => {
  const [isAdmin, setIsAdmin] = useState(localStorage.getItem('is_admin') === 'true');
  const [isAuthenticated, setIsAuthenticated] = useState(!!localStorage.getItem('auth_token'));
  const [userName, setUserName] = useState(localStorage.getItem('user_name') || '');
  const navigate = useNavigate();

  // Use localStorage first for instant rendering, then verify with API
  useEffect(() => {
    // Check authentication from localStorage first for quick rendering
    const token = localStorage.getItem('auth_token');
    const storedIsAdmin = localStorage.getItem('is_admin') === 'true';
    const storedName = localStorage.getItem('user_name');
    
    setIsAuthenticated(!!token);
    setIsAdmin(storedIsAdmin);
    setUserName(storedName || '');
    
    // Only make API call if we have a token
    if (token) {
      // Lightweight auth verification
      const verifyAuth = async () => {
        try {
          const user = await api.getCurrentUser();
          if (user) {
            // Update state if different from localStorage
            if (user.is_admin !== storedIsAdmin) {
              setIsAdmin(user.is_admin);
            }
            if (user.name && user.name !== storedName) {
              setUserName(user.name);
            }
          }
        } catch (error) {
          // If API call fails, rely on localStorage
          console.error('Auth verification error:', error);
        }
      };
      
      verifyAuth();
    }
    
    // Listen for auth changes
    const handleAuthChange = () => {
      const newToken = localStorage.getItem('auth_token');
      const newIsAdmin = localStorage.getItem('is_admin') === 'true';
      const newName = localStorage.getItem('user_name');
      
      setIsAuthenticated(!!newToken);
      setIsAdmin(newIsAdmin);
      setUserName(newName || '');
    };
    
    window.addEventListener('auth-change', handleAuthChange);
    
    return () => {
      window.removeEventListener('auth-change', handleAuthChange);
    };
  }, []);

  // Handle click on the SafeEats logo
  const handleLogoClick = (e) => {
    e.preventDefault();
    
    // For admins, go to restaurant list
    if (isAdmin) {
      navigate('/restaurant-list');
    }
    else if (isAuthenticated && !isAdmin) {
      navigate('/dashboard');
    }
    else {
      navigate('/');
    }
  };

  return (
    <header className="bg-white shadow-md py-6 px-8">
      <div className="container mx-auto flex items-center">
        {/* Logo/Brand */}
        <div className="flex items-center mr-10">
          <a href="#" onClick={handleLogoClick} className="font-bold text-xl text-[#8DB670]">
            SafeEats
          </a>
        </div>
        
        {/* Navigation links - only show if authenticated */}
        {isAuthenticated && (
          <nav className="hidden md:flex space-x-6 flex-grow">
            {!isAdmin && (
              <Link
                to="/dashboard"
                className="text-gray-700 hover:text-[#8DB670]"
              >
                My restaurants
              </Link>
            )}
            
            {/* Admin-only links */}
            {isAdmin && (
              <>
                <Link 
                  to="/restaurant-list" 
                  className="text-gray-700 hover:text-[#8DB670]"
                >
                  All Restaurants
                </Link>
                <Link 
                  to="/admin" 
                  className="text-gray-700 hover:text-[#8DB670]"
                >
                  Admin Panel
                </Link>
              </>
            )}
          </nav>
        )}
        
        {/* Profile Menu - push to the right */}
        <div className="ml-auto">
          <ProfileMenu isAdmin={isAdmin} userName={userName} />
        </div>
      </div>
    </header>
  );
};

export default Header;