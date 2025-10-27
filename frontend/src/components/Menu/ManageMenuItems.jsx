import React, { useState, useEffect, useRef } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import { api } from '../../services/api';
import MenuItemForm from './MenuItemForm';

const ManageMenuItems = () => {
  const [restaurants, setRestaurants] = useState([]);
  const [menuForms, setMenuForms] = useState([0]); // Start with a single form with index 0
  const [menuItemsData, setMenuItemsData] = useState({}); // Use an object with form indices as keys
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [ingestedItems, setIngestedItems] = useState([]);
  const [isIngesting, setIsIngesting] = useState(false);
  const [showConfirmDialog, setShowConfirmDialog] = useState(false);
  const [itemToDelete, setItemToDelete] = useState(null);
  const { restaurantId } = useParams(); // Get restaurantId from URL
  const navigate = useNavigate(); // Hook for navigation
  const lastFormRef = useRef(null); // Reference for the most recently added form element
  const shouldScrollToNew = useRef(false); // Track if we need to scroll after adding a new form

  // First, check authentication status
  useEffect(() => {
    const checkAuth = async () => {
      try {
        setLoading(true);
        const user = await api.getCurrentUser();
        
        if (!user) {
          // If not authenticated, redirect to login
          navigate('/', { state: { returnTo: `/restaurant/${restaurantId}/menu` } });
          return;
        }
        
        // Verify user has access to this restaurant
        const hasAccess = user.is_admin || user.restaurantId === restaurantId;
        if (!hasAccess) {
          navigate(`/restaurant/${user.restaurantId || ''}`);
          return;
        }
        
        // Once authenticated, fetch restaurants
        const response = await api.getRestaurants();
        setRestaurants(response);
        setLoading(false);
      } catch (error) {
        console.error("Authentication or fetch error", error);
        setError("Failed to load data. Please try again.");
        setLoading(false);
      }
    };
    
    checkAuth();
  }, [restaurantId, navigate]);

  // Handle navigation back to restaurant page
  const handleBackToRestaurant = () => {
    navigate(`/restaurant/${restaurantId}`);
  };

  const addMenuItem = () => {
    const newFormIndex = menuForms.length > 0 ? Math.max(...menuForms) + 1 : 0;
    setMenuForms([...menuForms, newFormIndex]);
    shouldScrollToNew.current = true;
  };

  const handleIngestFile = async (evt) => {
    const file = evt.target.files && evt.target.files[0];
    if (!file) return;
    setError('');
    setIsIngesting(true);
    try {
      const result = await api.ingestMenuImage(file);
      const items = (result && result.items) || [];
      setIngestedItems(items);
      // Insert rows into forms for quick editing
      const baseIndex = menuForms.length > 0 ? Math.max(...menuForms) + 1 : 0;
      const newIndices = items.map((_, i) => baseIndex + i);
      setMenuForms(prev => [...prev, ...newIndices]);
      // Seed form data
      setMenuItemsData(prev => {
        const next = { ...prev };
        newIndices.forEach((idx, i) => {
          const it = items[i] || {};
          next[idx] = {
            name: it.name || '',
            description: it.description || '',
            price: it.price || 0,
            priceNumeric: typeof it.price === 'number' ? it.price : 0,
            allergens: it.allergens || [],
            dietaryCategories: it.dietaryCategories || [],
            ingredients: it.ingredients || ''
          };
        });
        return next;
      });
    } catch (e) {
      setError(e?.message || 'Failed to ingest image');
    } finally {
      setIsIngesting(false);
      // reset file input value to allow re-uploading same file
      evt.target.value = '';
    }
  };

  useEffect(() => {
    if (shouldScrollToNew.current && lastFormRef.current) {
      lastFormRef.current.scrollIntoView({ behavior: 'smooth', block: 'start' });
      shouldScrollToNew.current = false;
    }
  }, [menuForms]); // Trigger when forms array changes


  // Modified to show confirmation dialog instead of removing immediately
  const confirmRemoveMenuItem = (indexToRemove) => {
    setItemToDelete(indexToRemove);
    setShowConfirmDialog(true);
  };

  // Actual removal happens here after confirmation
  const removeMenuItem = () => {
    if (itemToDelete !== null) {
      setMenuForms(menuForms.filter(index => index !== itemToDelete));
      
      // Also remove this form's data from menuItemsData
      setMenuItemsData(prevData => {
        const newData = { ...prevData };
        delete newData[itemToDelete];
        return newData;
      });

      // Close the dialog and reset the item to delete
      setShowConfirmDialog(false);
      setItemToDelete(null);
    }
  };

  // Cancel deletion
  const cancelRemoval = () => {
    setShowConfirmDialog(false);
    setItemToDelete(null);
  };

  // Update data for a specific form
  const handleFormChange = (index, data) => {
    setMenuItemsData(prevData => {
      // Only update if data has actually changed
      if (JSON.stringify(prevData[index]) !== JSON.stringify(data)) {
        return {
          ...prevData,
          [index]: data
        };
      }
      return prevData;
    });
  };

  // Handle the submission of all items at once
  const handleAddAllItems = async () => {
    if (!restaurantId) {
      setError('Restaurant ID is missing!');
      return;
    }

    // Convert object to array and filter out any undefined values
    const itemsToAdd = Object.values(menuItemsData).filter(item => 
      item && item.name && item.price // Basic validation
    );

    if (itemsToAdd.length === 0) {
      setError('No valid menu items to add!');
      return;
    }

    try {
      setLoading(true);
      console.log('Adding menu items:', itemsToAdd);

      // Use Promise.all to send all requests in parallel
      const addItemPromises = itemsToAdd.map((itemData) =>
        api.addMenuItem(restaurantId, itemData)
      );

      // Wait for all the promises to resolve
      await Promise.all(addItemPromises);

      // IMPORTANT: Store the success message in localStorage instead of sessionStorage
      // This is more reliable across page navigation
      localStorage.setItem('menuItemsAdded', 'true');
      localStorage.setItem('menuItemsAddedCount', itemsToAdd.length.toString());
      
      // Navigate back to restaurant page immediately without showing any dialog
      navigate(`/restaurant/${restaurantId}`);
      
    } catch (error) {
      console.error('Failed to add menu items', error);
      setError('Error adding menu items. Please try again.');
      setLoading(false);
    }
  };

  // Show loading state
  if (loading) {
    return (
      <div className="container mx-auto p-4 flex justify-center items-center min-h-[60vh]">
        <div className="animate-spin rounded-full h-12 w-12 border-t-2 border-b-2 border-[#8DB670]"></div>
      </div>
    );
  }

  return (
    <div className="container mx-auto p-4">
      <div className="relative flex w-full mb-6">
        <button 
          onClick={handleBackToRestaurant}
          className="bg-gray-500 hover:bg-gray-600 text-white py-2 px-4 rounded-md flex items-center"
        >
          <span className="mr-1">←</span> Back to Restaurant
        </button>
        <h1 className="absolute left-[41%] text-3xl font-bold">Add Menu Items</h1>
      </div>

      {error && (
        <div className="bg-red-100 border border-red-400 text-red-700 px-4 py-3 rounded mb-4">
          {error}
        </div>
      )}

      <div className='flex flex-col justify-center items-center'>
        <div className="w-[55%] mb-6">
          <label className="block font-medium mb-2">Import menu from photo (PNG/JPEG)</label>
          <input type="file" accept="image/png, image/jpeg, application/pdf" onChange={handleIngestFile} />
          {isIngesting && (
            <div className="text-sm text-gray-600 mt-2">Extracting items...</div>
          )}
          {ingestedItems.length > 0 && (
            <div className="text-sm text-gray-700 mt-2">Imported {ingestedItems.length} items. Review and edit below, then click "Add All Items".</div>
          )}
        </div>
        {menuForms.map((formIndex, arrayIndex) => (
          <div
            key={formIndex}
            ref={arrayIndex === menuForms.length - 1 ? lastFormRef : null}>
            <MenuItemForm
              formIndex={formIndex}
              restaurantOptions={restaurants}
              onRemove={() => confirmRemoveMenuItem(formIndex)}
              onFormChange={(data) => handleFormChange(formIndex, data)}
              initialData={menuItemsData[formIndex] || {}}
            />
          </div>
        ))}
      </div>

      <div className='w-full flex flex-col justify-center items-center'>
        <div className="w-[55%]">
          <button 
              onClick={addMenuItem} 
              className="block w-12 h-12 float-right bg-[#8DB670] rounded-full hover:bg-[#6c8b55] justify-items-center"
              title="Add another item"
            >
              <svg xmlns="http://www.w3.org/2000/svg" width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="#ffffff" strokeWidth="5" strokeLinecap="round" strokeLinejoin="round"><line x1="12" y1="5" x2="12" y2="19"></line><line x1="5" y1="12" x2="19" y2="12"></line></svg>
          </button>
          <div className='flex flex-col justify-center items-center gap-6 mt-10'>
            <button
              onClick={handleAddAllItems}
              disabled={loading}
              className="block w-full max-w-96 text-center bg-[#8DB670] rounded-xl pt-4 pb-4 font-semibold text-white mt-2 hover:bg-[#6c8b55] disabled:bg-gray-400"
            >
              {loading ? 'Adding Items...' : 'Add All Items'}
            </button>

            <button
              onClick={handleBackToRestaurant}
              className="bg-gray-500 text-white py-2 px-4 rounded-md hover:bg-gray-600"
            >
              Cancel
            </button>
          </div>
        </div>
      </div>

      {/* Confirmation Dialog for item deletion - Styled like UserManagement */}
      {showConfirmDialog && (
        <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50">
          <div className="bg-white rounded-lg p-6 max-w-md w-full">
            <h3 className="text-lg font-medium text-gray-900 mb-4">Confirm Deletion</h3>
            <p className="text-gray-600 mb-6">
              Are you sure you want to delete this menu item? This action cannot be undone.
            </p>
            <div className="flex justify-end space-x-3">
              <button
                onClick={cancelRemoval}
                className="px-4 py-2 border border-gray-300 rounded-md shadow-sm text-sm font-medium text-gray-700 bg-white hover:bg-gray-50"
              >
                Cancel
              </button>
              <button
                onClick={removeMenuItem}
                className="px-4 py-2 rounded-md shadow-sm text-sm font-medium text-white bg-red-600 hover:bg-red-700"
              >
                Yes, Delete
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};

export default ManageMenuItems;