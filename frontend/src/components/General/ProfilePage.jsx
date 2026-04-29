import React, { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import { api } from '../../services/api';

const ProfilePage = () => {
  const [user, setUser] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const navigate = useNavigate();

  useEffect(() => {
    // Check if user is authenticated
    const token = localStorage.getItem('auth_token');
    if (!token) {
      navigate('/');
      return;
    }

    // Fetch user profile data
    const fetchUserProfile = async () => {
      try {
        setLoading(true);
        setError(null);
        const userData = await api.getCurrentUser();
        
        if (userData && userData.email) {
          setUser(userData);
        } else {
          setError('Unable to load profile information');
        }
      } catch (error) {
        console.error('Error fetching user profile:', error);
        setError('Error loading profile. Please try again later.');
        
        // If unauthorized, redirect to login
        if (error.response && (error.response.status === 401 || error.response.status === 403)) {
          localStorage.removeItem('auth_token');
          navigate('/');
        }
      } finally {
        setLoading(false);
      }
    };

    fetchUserProfile();
  }, [navigate]);

  if (loading) {
    return (
      <div className="container mx-auto px-4 py-8">
        <div className="bg-white rounded-lg shadow-md p-6 max-w-3xl mx-auto">
          <p className="text-center text-gray-500">Loading profile information...</p>
        </div>
      </div>
    );
  }

  if (error) {
    return (
      <div className="container mx-auto px-4 py-8">
        <div className="bg-white rounded-lg shadow-md p-6 max-w-3xl mx-auto">
          <p className="text-center text-red-500">{error}</p>
          <div className="mt-4 text-center">
            <button
              onClick={() =>
                navigate(localStorage.getItem('is_admin') === 'true' ? '/restaurant-list' : '/dashboard')
              }
              className="px-4 py-2 bg-gray-200 rounded hover:bg-gray-300"
            >
              Return to dashboard
            </button>
          </div>
        </div>
      </div>
    );
  }

  return (
    <div className="container mx-auto px-4 py-8 font-[Roboto_Flex]">
      <div className="bg-white rounded-lg shadow-md p-6 max-w-3xl mx-auto">
        <h1 className="text-2xl font-bold text-center mb-6">My Profile</h1>
        
        {/* Profile information */}
        <div className="mb-6">
          <div className="mx-auto w-20 h-20 rounded-full bg-[#8DB670] text-white flex items-center justify-center text-2xl font-semibold mb-4">
            {user?.email?.charAt(0).toUpperCase() || '?'}
          </div>
          
          <div className="space-y-4">
            <div className="border-b pb-2">
              <p className="text-sm text-gray-600">Email</p>
              <p className="font-medium">{user?.email || 'No email available'}</p>
            </div>
            
            {user?.name && (
              <div className="border-b pb-2">
                <p className="text-sm text-gray-600">Name</p>
                <p className="font-medium">{user.name}</p>
              </div>
            )}
            
            <div className="border-b pb-2">
              <p className="text-sm text-gray-600">Role</p>
              <p className="font-medium capitalize">{user?.is_admin ? 'Administrator' : 'User'}</p>
            </div>
            
            {user?.restaurantId && (
              <div className="border-b pb-2">
                <p className="text-sm text-gray-600">Restaurant ID</p>
                <p className="font-medium">{user.restaurantId}</p>
              </div>
            )}
          </div>
        </div>
        
        {/* Actions */}
        <div className="flex justify-center mt-6">
          <button
            onClick={() => navigate(user?.is_admin ? '/restaurant-list' : '/dashboard')}
            className="px-4 py-2 text-white bg-[#8DB670] rounded hover:bg-[#6c8b55]"
          >
            Back to dashboard
          </button>
        </div>
      </div>
    </div>
  );
};

export default ProfilePage;