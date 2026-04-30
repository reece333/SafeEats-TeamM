import React, { useState, useEffect } from 'react';
import { useNavigate, useLocation, Link } from 'react-router-dom';
import { Capacitor } from '@capacitor/core';
import { Toast } from '@capacitor/toast';
import { api } from '../../services/api';

const RegisterRestaurant = () => {
  const navigate = useNavigate();
  const location = useLocation();
  const isAddRestaurantRoute = location.pathname === '/add-restaurant';

  const [userData, setUserData] = useState({
    name: '',
    email: location.state?.email || '',
    password: location.state?.password || '',
    confirmPassword: ''
  });

  const [restaurantData, setRestaurantData] = useState({
    name: '',
    address: '',
    phone: '',
    cuisine_type: ''
  });

  const [error, setError] = useState('');
  const [success, setSuccess] = useState('');
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    const checkAuth = async () => {
      if (isAddRestaurantRoute) {
        const token = localStorage.getItem('auth_token');
        if (!token) {
          navigate('/', { replace: true });
        }
        return;
      }
      const token = localStorage.getItem('auth_token');
      if (token) {
        const user = await api.getCurrentUser();
        if (user) {
          navigate('/dashboard', { replace: true });
        }
      }
    };
    checkAuth();
  }, [navigate, isAddRestaurantRoute]);

  const showToast = async (message) => {
    if (Capacitor.isNativePlatform()) {
      await Toast.show({
        text: message,
        duration: 'short',
        position: 'bottom'
      });
    }
  };

  const handleUserSubmit = async (e) => {
    e.preventDefault();

    if (!userData.name.trim()) {
      setError('Please enter your name');
      await showToast('Please enter your name');
      return;
    }

    if (userData.password !== userData.confirmPassword) {
      setError('Passwords do not match');
      await showToast('Passwords do not match');
      return;
    }

    if (userData.password.length < 6) {
      setError('Password must be at least 6 characters');
      await showToast('Password must be at least 6 characters');
      return;
    }

    setLoading(true);
    setError('');

    try {
      await api.registerUser({
        name: userData.name,
        email: userData.email,
        password: userData.password,
        restaurantName: ''
      });
      await showToast('Account created!');
      navigate('/dashboard', { replace: true });
    } catch (err) {
      setError(err.message || 'Registration failed');
      await showToast(err.message || 'Registration failed');
    } finally {
      setLoading(false);
    }
  };

  const handleRestaurantSubmit = async (e) => {
    e.preventDefault();
    setLoading(true);
    setError('');

    try {
      const response = await api.createRestaurant(restaurantData);
      setSuccess('Restaurant registered successfully!');
      await showToast('Restaurant registered successfully!');
      setTimeout(() => {
        navigate(`/restaurant/${response.id}`);
      }, 400);
    } catch (err) {
      setError(err.message || 'Failed to create restaurant');
      await showToast(err.message || 'Failed to create restaurant');
    } finally {
      setLoading(false);
    }
  };

  const pageTitle = isAddRestaurantRoute ? 'Add a restaurant' : 'Create your account';
  const subTitle = isAddRestaurantRoute
    ? 'Register a venue you manage. You can add more later from your dashboard.'
    : 'Sign up first. You can register a restaurant or join a team whenever you are ready.';

  return (
    <div className="w-full p-6 font-[Roboto_Flex]">
      <h1 className="text-3xl font-bold text-center">{pageTitle}</h1>
      <p className="text-center text-gray-600 mt-2 max-w-lg mx-auto">{subTitle}</p>

      {error && <div className="bg-red-100 border border-red-400 text-red-700 px-4 py-3 rounded mb-4 max-w-lg mx-auto mt-4">{error}</div>}
      {success && <div className="bg-green-100 border border-green-400 text-green-700 px-4 py-3 rounded mb-4 max-w-lg mx-auto mt-4">{success}</div>}

      <div className="flex flex-col items-center justify-center mt-10">
        <div className="w-full max-w-lg bg-white p-8 rounded-xl shadow-md">
          {!isAddRestaurantRoute && (
            <>
              <h2 className="text-2xl font-bold mb-6 text-center">Account details</h2>
              <form onSubmit={handleUserSubmit}>
                <div className="mb-4">
                  <label className="block text-lg mb-2">Name*</label>
                  <input
                    type="text"
                    placeholder="Enter your full name"
                    className="w-full p-3 border border-gray-300 rounded-xl"
                    value={userData.name}
                    onChange={(e) => setUserData({ ...userData, name: e.target.value })}
                    required
                  />
                </div>

                <div className="mb-4">
                  <label className="block text-lg mb-2">Email*</label>
                  <input
                    type="email"
                    placeholder="Enter your email"
                    className="w-full p-3 border border-gray-300 rounded-xl"
                    value={userData.email}
                    onChange={(e) => setUserData({ ...userData, email: e.target.value })}
                    required
                  />
                </div>

                <div className="mb-4">
                  <label className="block text-lg mb-2">Password*</label>
                  <input
                    type="password"
                    placeholder="Create a password"
                    className="w-full p-3 border border-gray-300 rounded-xl"
                    value={userData.password}
                    onChange={(e) => setUserData({ ...userData, password: e.target.value })}
                    required
                  />
                </div>

                <div className="mb-6">
                  <label className="block text-lg mb-2">Confirm Password*</label>
                  <input
                    type="password"
                    placeholder="Confirm your password"
                    className="w-full p-3 border border-gray-300 rounded-xl"
                    value={userData.confirmPassword}
                    onChange={(e) => setUserData({ ...userData, confirmPassword: e.target.value })}
                    required
                  />
                </div>

                <button
                  type="submit"
                  disabled={loading}
                  className="w-full text-center bg-[#8DB670] rounded-xl py-3 font-semibold text-white hover:bg-[#6c8b55] disabled:bg-gray-400"
                >
                  {loading ? 'Creating account…' : 'Create account'}
                </button>

                <div className="mt-4 text-center">
                  <button
                    type="button"
                    onClick={() => navigate('/')}
                    className="text-gray-500 hover:underline"
                  >
                    Already have an account? Sign in
                  </button>
                </div>
              </form>
            </>
          )}

          {isAddRestaurantRoute && (
            <>
              <div className="mb-4">
                <Link to="/dashboard" className="text-sm text-[#8DB670] hover:underline">
                  ← Back to my restaurants
                </Link>
              </div>
              <h2 className="text-2xl font-bold mb-6 text-center">Restaurant details</h2>
              <form onSubmit={handleRestaurantSubmit}>
                <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                  <div>
                    <label className="block text-lg mb-2">Restaurant Name*</label>
                    <input
                      className="w-full p-3 border border-gray-300 rounded-xl"
                      placeholder="Restaurant Name"
                      value={restaurantData.name}
                      onChange={(e) => setRestaurantData({ ...restaurantData, name: e.target.value })}
                      required
                    />
                  </div>

                  <div>
                    <label className="block text-lg mb-2">Phone Number*</label>
                    <input
                      className="w-full p-3 border border-gray-300 rounded-xl"
                      placeholder="Phone"
                      value={restaurantData.phone}
                      onChange={(e) => setRestaurantData({ ...restaurantData, phone: e.target.value })}
                      required
                    />
                  </div>

                  <div>
                    <label className="block text-lg mb-2">Address*</label>
                    <input
                      className="w-full p-3 border border-gray-300 rounded-xl"
                      placeholder="Address"
                      value={restaurantData.address}
                      onChange={(e) => setRestaurantData({ ...restaurantData, address: e.target.value })}
                      required
                    />
                  </div>

                  <div>
                    <label className="block text-lg mb-2">Cuisine Type*</label>
                    <input
                      className="w-full p-3 border border-gray-300 rounded-xl"
                      placeholder="Cuisine Type"
                      value={restaurantData.cuisine_type}
                      onChange={(e) => setRestaurantData({ ...restaurantData, cuisine_type: e.target.value })}
                      required
                    />
                  </div>
                </div>

                <div className="mt-6">
                  <button
                    type="submit"
                    disabled={loading}
                    className="w-full text-center bg-[#8DB670] rounded-xl py-3 font-semibold text-white hover:bg-[#6c8b55] disabled:bg-gray-400"
                  >
                    {loading ? 'Saving…' : 'Register restaurant'}
                  </button>
                </div>
              </form>
            </>
          )}
        </div>
      </div>
    </div>
  );
};

export default RegisterRestaurant;
