import { Capacitor } from '@capacitor/core';
import { CapacitorHttp } from '@capacitor/core';

const getBaseUrl = () => {
  // Check if running locally
  if (window.location.hostname === 'localhost') {
    return 'http://localhost:8000';
  }
  
  // When deployed on Render
  return 'https://restaurant-allergy-manager-backend.onrender.com'; 
};

const BASE_URL = getBaseUrl();

console.log('Using API URL:', BASE_URL);

// Helper for getting auth token
const getAuthToken = () => {
  return localStorage.getItem('auth_token');
};

// Set authentication token
const setAuthToken = (token) => {
  localStorage.setItem('auth_token', token);
};

// Set user ID
const setUserId = (uid) => {
  localStorage.setItem('user_id', uid);
};

// Get user ID
const getUserId = () => {
  return localStorage.getItem('user_id');
};

// Set user email
const setUserEmail = (email) => {
  if (email) {
    localStorage.setItem('email', email);
  }
};

// Get user email
const getUserEmail = () => {
  return localStorage.getItem('email');
};

// Set user name
const setUserName = (name) => {
  if (name) {
    localStorage.setItem('user_name', name);
  }
};

// Get user name
const getUserName = () => {
  return localStorage.getItem('user_name');
};

// Set user role
const setUserRole = (isAdmin) => {
  localStorage.setItem('is_admin', isAdmin ? 'true' : 'false');
};

// Get user role
const isUserAdmin = () => {
  return localStorage.getItem('is_admin') === 'true';
};

// Clear authentication data
const clearAuthData = () => {
  localStorage.removeItem('auth_token');
  localStorage.removeItem('user_id');
  localStorage.removeItem('user_name');
  localStorage.removeItem('email');
  localStorage.removeItem('restaurant_id');
  localStorage.removeItem('is_admin');
};

// Set restaurant ID
const setRestaurantId = (restaurantId) => {
  if (restaurantId) {
    localStorage.setItem('restaurant_id', restaurantId);
  }
};

// Get restaurant ID
const getRestaurantId = () => {
  return localStorage.getItem('restaurant_id');
};

// Trigger auth change event - to notify components
const triggerAuthChange = () => {
  window.dispatchEvent(new CustomEvent('auth-change'));
};

// HTTP request wrapper with authorization
const httpRequest = async (options) => {
  try {
    // Add authorization header if not already set
    if (!options.headers?.Authorization) {
      const token = getAuthToken();
      if (token) {
        if (!options.headers) {
          options.headers = {};
        }
        options.headers['Authorization'] = `Bearer ${token}`;
      }
    }
    
    const response = await CapacitorHttp.request(options);
    
    // Handle unauthorized responses
    if (response.status === 401) {
      console.warn('Received 401 Unauthorized response');
      // Clear auth data
      clearAuthData();
      // Trigger auth change event
      triggerAuthChange();
      // Throw error to be caught by caller
      throw new Error('Your session has expired. Please log in again.');
    }
    
    // Handle forbidden responses
    if (response.status === 403) {
      console.warn('Received 403 Forbidden response');
      // Throw error to be caught by caller
      throw new Error('You do not have permission to access this resource.');
    }
    
    return response;
  } catch (error) {
    console.error('HTTP request error:', error);
    throw error;
  }
};

export const api = {
  // Authentication methods
  registerUser: async (userData) => {
    try {
      const response = await CapacitorHttp.request({
        method: 'POST',
        url: `${BASE_URL}/auth/register`,
        headers: {
          'Content-Type': 'application/json',
          'Accept': 'application/json'
        },
        data: userData
      });
      
      if (response.status !== 200) {
        const errorData = response.data;
        throw new Error(errorData?.detail || 'Registration failed');
      }
      
      // Store token and user data directly
      setAuthToken(response.data.token);
      setUserId(response.data.uid);
      setUserEmail(response.data.email);
      setUserName(response.data.name);
      setUserRole(response.data.is_admin);
      
      if (response.data.restaurantId) {
        setRestaurantId(response.data.restaurantId);
      }
      
      // Trigger auth change event
      triggerAuthChange();
      
      return response.data;
    } catch (error) {
      console.error('Registration error:', error);
      throw error;
    }
  },
  
  loginUser: async (email, password) => {
    try {
      console.log('Attempting login with email:', email);
      
      const response = await CapacitorHttp.request({
        method: 'POST',
        url: `${BASE_URL}/auth/login`,
        headers: {
          'Content-Type': 'application/json',
          'Accept': 'application/json'
        },
        data: { email, password }
      });
      
      console.log('Login response status:', response.status);
      
      if (response.status !== 200) {
        const errorData = response.data;
        throw new Error(errorData?.detail || 'Login failed');
      }
      
      console.log('Login successful, storing token and user data');
      
      // Store token and user data directly
      setAuthToken(response.data.token);
      setUserId(response.data.uid);
      setUserEmail(response.data.email);
      setUserName(response.data.name);
      setUserRole(response.data.is_admin);
      
      if (response.data.restaurantId) {
        setRestaurantId(response.data.restaurantId);
      }
      
      // Trigger auth change event
      triggerAuthChange();
      
      return response.data;
    } catch (error) {
      console.error('Login error:', error);
      throw error;
    }
  },
  
  logoutUser: async () => {
    try {
      // Call the logout endpoint if we have a token
      const token = getAuthToken();
      if (token) {
        await httpRequest({
          method: 'POST',
          url: `${BASE_URL}/auth/logout`,
          headers: {
            'Accept': 'application/json'
          }
        });
      }
    } catch (error) {
      console.error('Logout error:', error);
    } finally {
      // Always clear local auth data
      clearAuthData();
      
      // Trigger auth change event
      triggerAuthChange();
    }
  },
  
  getCurrentUser: async () => {
    const token = getAuthToken();
    if (!token) {
      return null;
    }
    
    try {
      const response = await httpRequest({
        method: 'GET',
        url: `${BASE_URL}/auth/user`,
        headers: {
          'Accept': 'application/json'
        }
      });
      
      if (response.status !== 200) {
        clearAuthData();
        triggerAuthChange();
        throw new Error(response.data?.detail || 'Failed to get user data');
      }
      
      // Store user data
      setUserRole(response.data.is_admin);
      setUserName(response.data.name);
      setUserEmail(response.data.email);
      
      // Update stored restaurant ID if it exists
      if (response.data.restaurantId) {
        setRestaurantId(response.data.restaurantId);
      }
      
      return response.data;
    } catch (error) {
      console.error('Error getting current user:', error);
      clearAuthData();
      triggerAuthChange();
      return null;
    }
  },
  
  // User management methods (admin only)
  getAllUsers: async () => {
    try {
      const response = await httpRequest({
        method: 'GET',
        url: `${BASE_URL}/auth/users`,
        headers: {
          'Accept': 'application/json'
        }
      });
      
      if (response.status !== 200) {
        throw new Error(response.data?.detail || 'Failed to fetch users');
      }
      
      return response.data;
    } catch (error) {
      console.error('Error fetching users:', error);
      throw error;
    }
  },
  
  makeUserAdmin: async (userId) => {
    try {
      const response = await httpRequest({
        method: 'POST',
        url: `${BASE_URL}/auth/make-admin/${userId}`,
        headers: {
          'Accept': 'application/json'
        }
      });
      
      if (response.status !== 200) {
        throw new Error(response.data?.detail || 'Failed to update user role');
      }
      
      return response.data;
    } catch (error) {
      console.error('Error making user admin:', error);
      throw error;
    }
  },
  
  makeUserAdminByEmail: async (email) => {
    try {
      const response = await httpRequest({
        method: 'POST',
        url: `${BASE_URL}/auth/make-admin-by-email`,
        headers: {
          'Content-Type': 'application/json',
          'Accept': 'application/json'
        },
        data: { email }
      });
      
      if (response.status !== 200) {
        throw new Error(response.data?.detail || 'Failed to update user role');
      }
      
      return response.data;
    } catch (error) {
      console.error('Error making user admin:', error);
      throw error;
    }
  },
  
  // Restaurant management methods
  createRestaurant: async (restaurantData) => {
    try {
      // Add owner_uid to restaurant data
      const uid = getUserId();
      const enrichedData = {
        ...restaurantData,
        owner_uid: uid
      };
      
      const response = await httpRequest({
        method: 'POST',
        url: `${BASE_URL}/restaurants/`,
        headers: {
          'Content-Type': 'application/json',
          'Accept': 'application/json'
        },
        data: enrichedData
      });
      
      if (response.status !== 200) {
        throw new Error(response.data?.detail || 'Failed to create restaurant');
      }
      
      // Store the restaurant ID
      if (response.data.id) {
        setRestaurantId(response.data.id);
        triggerAuthChange();
      }
      
      return response.data;
    } catch (error) {
      console.error('Error creating restaurant:', error);
      throw error;
    }
  },

  updateRestaurant: async (restaurantId, restaurantData) => {
    try {
      const response = await httpRequest({
        method: 'PUT',
        url: `${BASE_URL}/restaurants/${restaurantId}`,
        headers: {
          'Content-Type': 'application/json',
          'Accept': 'application/json'
        },
        data: restaurantData
      });

      if (response.status !== 200) {
        throw new Error(response.data?.detail || 'Failed to update restaurant');
      }

      return response.data;
    } catch (error) {
      console.error('Error updating restaurant:', error);
      throw error;
    }
  },

  getRestaurants: async () => {
    try {
      const response = await httpRequest({
        method: 'GET',
        url: `${BASE_URL}/restaurants`,
        headers: {
          'Accept': 'application/json'
        }
      });
      
      if (response.status !== 200) {
        throw new Error(response.data?.detail || 'Failed to fetch restaurants');
      }
      
      return response.data;
    } catch (error) {
      console.error('Error fetching restaurants:', error);
      throw error;
    }
  },

  addMenuItem: async (restaurantId, menuItemData) => {
    try {
      const response = await httpRequest({
        method: 'POST',
        url: `${BASE_URL}/restaurants/${restaurantId}/menu`,
        headers: {
          'Content-Type': 'application/json',
          'Accept': 'application/json'
        },
        data: menuItemData
      });
      
      if (response.status !== 200) {
        throw new Error(response.data?.detail || 'Failed to add menu item');
      }
      
      return response.data;
    } catch (error) {
      console.error('Error adding menu item:', error);
      throw error;
    }
  },

  getMenuItems: async (restaurantId, filters = {}) => {
    try {
      const { dietaryCategory, allergenFree } = filters;
      let url = `${BASE_URL}/restaurants/${restaurantId}/menu`;
      
      // Add query parameters if filters are provided
      const queryParams = new URLSearchParams();
      if (dietaryCategory) {
        queryParams.append('dietary_category', dietaryCategory);
      }
      if (allergenFree && allergenFree.length > 0) {
        allergenFree.forEach(allergen => {
          queryParams.append('allergen_free', allergen);
        });
      }
      
      const queryString = queryParams.toString();
      if (queryString) {
        url += `?${queryString}`;
      }

      const response = await httpRequest({
        method: 'GET',
        url,
        headers: {
          'Accept': 'application/json'
        }
      });
      
      if (response.status !== 200) {
        throw new Error(response.data?.detail || 'Failed to fetch menu items');
      }
      
      return response.data;
    } catch (error) {
      console.error('Error fetching menu items:', error);
      throw error;
    }
  },

  // AI parsing
  parseIngredientsWithAI: async (ingredientsText) => {
    try {
      const response = await httpRequest({
        method: 'POST',
        url: `${BASE_URL}/ai/parse-ingredients`,
        headers: {
          'Content-Type': 'application/json',
          'Accept': 'application/json'
        },
        data: { ingredients: ingredientsText }
      });

      if (response.status !== 200) {
        throw new Error(response.data?.detail || 'Failed to parse ingredients');
      }

      return response.data;
    } catch (error) {
      console.error('AI parsing error:', error);
      throw error;
    }
  },

  // Menu image ingestion
  ingestMenuImage: async (file) => {
    try {
      const formData = new FormData();
      formData.append('file', file);

      const token = getAuthToken();
      if (!token) {
        throw new Error('Authentication required');
      }

      const response = await fetch(`${BASE_URL}/ai/ingest-menu`, {
        method: 'POST',
        headers: {
          'Authorization': `Bearer ${token}`
        },
        body: formData
      });

      if (!response.ok) {
        const errorData = await response.json().catch(() => ({}));
        throw new Error(errorData?.detail || 'Failed to ingest menu image');
      }

      const data = await response.json();
      return data;
    } catch (error) {
      console.error('Menu ingestion error:', error);
      throw error;
    }
  },

  removeUserAdmin: async (email) => {
    try {
      const response = await httpRequest({
        method: 'POST',
        url: `${BASE_URL}/auth/remove-admin-by-email`,
        headers: {
          'Content-Type': 'application/json',
          'Accept': 'application/json'
        },
        data: { email }
      });
      
      if (response.status !== 200) {
        throw new Error(response.data?.detail || 'Failed to update user role');
      }
      
      return response.data;
    } catch (error) {
      console.error('Error removing admin privileges:', error);
      throw error;
    }
  },
  
  // User role and data helpers
  isAdmin: () => {
    return isUserAdmin();
  },
  
  getUserName: () => {
    return getUserName();
  },
  
  // Debug helper
  debugAuthState: () => {
    const token = getAuthToken();
    const userId = getUserId();
    const userEmail = getUserEmail();
    const userName = getUserName();
    const restaurantId = getRestaurantId();
    const isAdmin = isUserAdmin();
    
    console.group('Authentication State Debug');
    console.log('Has token:', !!token);
    if (token) {
      console.log('Token length:', token.length);
      console.log('Token preview:', token.substring(0, 10) + '...');
    }
    console.log('User ID:', userId || 'None');
    console.log('User Email:', userEmail || 'None');
    console.log('User Name:', userName || 'None');
    console.log('Restaurant ID:', restaurantId || 'None');
    console.log('Is Admin:', isAdmin);
    console.groupEnd();
    
    return {
      isAuthenticated: !!token,
      hasUserId: !!userId,
      hasUserEmail: !!userEmail,
      hasUserName: !!userName,
      hasRestaurantId: !!restaurantId,
      isAdmin: isAdmin
    };
  },
  
  updateMenuItem: async (restaurantId, menuItemId, menuItemData) => {
    try {
      const response = await CapacitorHttp.request({
        method: 'PUT',
        url: `${BASE_URL}/restaurants/${restaurantId}/menu/${menuItemId}`,
        headers: {
          'Content-Type': 'application/json',
          'Accept': 'application/json'
        },
        data: menuItemData
      });
      
      if (response.status !== 200) {
        const errorData = response.data;
        throw new Error(errorData?.detail || 'Failed to update menu item');
      }
      
      return response.data;
    } catch (error) {
      console.error('Error updating menu item:', error);
      throw error;
    }
  },

  deleteMenuItem: async (restaurantId, menuItemId) => {
    try {
      const response = await CapacitorHttp.request({
        method: 'DELETE',
        url: `${BASE_URL}/restaurants/${restaurantId}/menu/${menuItemId}`,
        headers: {
          'Accept': 'application/json'
        }
      });
      
      if (response.status !== 200) {
        const errorData = response.data;
        throw new Error(errorData?.detail || 'Failed to delete menu item');
      }
      
      return response.data;
    } catch (error) {
      console.error('Error deleting menu item:', error);
      throw error;
    }
  }
};
