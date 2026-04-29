import React, { useState, useEffect, useRef } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import { api } from '../../services/api';
import MenuItemForm from './MenuItemForm';

const allergenOptions = [
  { id: 'milk', label: 'Milk' },
  { id: 'eggs', label: 'Eggs' },
  { id: 'fish', label: 'Fish' },
  { id: 'tree_nuts', label: 'Tree Nuts' },
  { id: 'wheat', label: 'Wheat' },
  { id: 'shellfish', label: 'Shellfish' },
  { id: 'gluten_free', label: 'Gluten-Free' },
  { id: 'peanuts', label: 'Peanuts' },
  { id: 'soybeans', label: 'Soybeans' },
  { id: 'sesame', label: 'Sesame' }
];

const dietaryCategories = [
  { id: 'vegan', label: 'Vegan' },
  { id: 'vegetarian', label: 'Vegetarian' }
];

const ManageMenuItems = () => {
  const [restaurants, setRestaurants] = useState([]);
  const [menuItems, setMenuItems] = useState([]);
  const [menuForms, setMenuForms] = useState([0]); // Start with a single form with index 0
  const [menuItemsData, setMenuItemsData] = useState({}); // Use an object with form indices as keys
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [ingestedItems, setIngestedItems] = useState([]);
  const [isIngesting, setIsIngesting] = useState(false);
  const [showConfirmDialog, setShowConfirmDialog] = useState(false);
  const [itemToDelete, setItemToDelete] = useState(null);
  const [showArchived, setShowArchived] = useState(false);
  const [selectedItemIds, setSelectedItemIds] = useState([]);
  const [bulkDraft, setBulkDraft] = useState({
    addAllergens: [],
    removeAllergens: [],
    addDietaryCategories: [],
    removeDietaryCategories: []
  });
  const [showBulkConfirmDialog, setShowBulkConfirmDialog] = useState(false);
  const [isApplyingBulkUpdate, setIsApplyingBulkUpdate] = useState(false);
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
        
        // Verify user has access (manager, staff, or admin)
        const hasAccess = user.is_admin || (user.restaurants && user.restaurants.some(r => String(r.id) === String(restaurantId)));
        if (!hasAccess) {
          navigate('/dashboard');
          return;
        }
        
        // Once authenticated, fetch restaurants
        const response = await api.getRestaurants();
        setRestaurants(response);
        const menuResponse = await api.getMenuItems(restaurantId);
        setMenuItems(menuResponse || []);
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

  const refreshMenuItems = async () => {
    const menuResponse = await api.getMenuItems(restaurantId);
    setMenuItems(menuResponse || []);
  };

  const visibleMenuItems = menuItems.filter((item) => showArchived || !item.archived);

  const clearBulkDraft = () => {
    setBulkDraft({
      addAllergens: [],
      removeAllergens: [],
      addDietaryCategories: [],
      removeDietaryCategories: []
    });
  };

  const toggleSelectedItem = (itemId) => {
    setSelectedItemIds((prev) => (
      prev.includes(itemId)
        ? prev.filter((selectedId) => selectedId !== itemId)
        : [...prev, itemId]
    ));
  };

  const toggleBulkValue = (key, value) => {
    setBulkDraft((prev) => ({
      ...prev,
      [key]: prev[key].includes(value)
        ? prev[key].filter((entry) => entry !== value)
        : [...prev[key], value]
    }));
  };

  const bulkSummary = {
    count: selectedItemIds.length,
    addAllergens: bulkDraft.addAllergens,
    removeAllergens: bulkDraft.removeAllergens,
    addDietaryCategories: bulkDraft.addDietaryCategories,
    removeDietaryCategories: bulkDraft.removeDietaryCategories
  };

  const exportCsv = () => {
    const headers = ['name', 'description', 'price', 'ingredients', 'allergen_tags', 'dietary_labels'];
    const rows = visibleMenuItems.filter((item) => !item.archived).map((item) => ([
      item.name || '',
      item.description || '',
      typeof item.price === 'number' ? item.price.toFixed(2) : String(item.price ?? ''),
      item.ingredients || '',
      (item.allergens || []).join('; '),
      (item.dietaryCategories || []).join('; ')
    ]));

    const escapeCsv = (value) => {
      const text = String(value ?? '');
      return /[",\n]/.test(text) ? `"${text.replace(/"/g, '""')}"` : text;
    };

    const csv = [headers, ...rows].map((row) => row.map(escapeCsv).join(',')).join('\n');
    const blob = new Blob([csv], { type: 'text/csv;charset=utf-8;' });
    const url = URL.createObjectURL(blob);
    const link = document.createElement('a');
    link.href = url;
    link.download = `safeeats-menu-${restaurantId || 'export'}.csv`;
    link.click();
    URL.revokeObjectURL(url);
  };

  const duplicateMenuItem = async (itemId) => {
    try {
      const duplicated = await api.duplicateMenuItem(restaurantId, itemId);
      setMenuItems((prev) => [duplicated, ...prev]);
    } catch (dupError) {
      setError(dupError?.message || 'Failed to duplicate menu item');
    }
  };

  const toggleArchiveMenuItem = async (item) => {
    try {
      const updated = item.archived
        ? await api.restoreMenuItem(restaurantId, item.id)
        : await api.archiveMenuItem(restaurantId, item.id);

      setMenuItems((prev) => prev.map((entry) => (entry.id === updated.id ? updated : entry)));
    } catch (archiveError) {
      setError(archiveError?.message || 'Failed to update menu item status');
    }
  };

  const openBulkConfirmDialog = () => {
    if (selectedItemIds.length === 0) {
      setError('Select one or more menu items first.');
      return;
    }

    const hasChanges = Object.values(bulkDraft).some((values) => values.length > 0);
    if (!hasChanges) {
      setError('Choose at least one tag change before applying bulk edits.');
      return;
    }

    setError('');
    setShowBulkConfirmDialog(true);
  };

  const applyBulkUpdate = async () => {
    try {
      setIsApplyingBulkUpdate(true);
      await api.bulkUpdateMenuItems(restaurantId, {
        item_ids: selectedItemIds,
        add_allergens: bulkDraft.addAllergens,
        remove_allergens: bulkDraft.removeAllergens,
        add_dietary_categories: bulkDraft.addDietaryCategories,
        remove_dietary_categories: bulkDraft.removeDietaryCategories
      });
      await refreshMenuItems();
      setSelectedItemIds([]);
      clearBulkDraft();
      setShowBulkConfirmDialog(false);
    } catch (bulkError) {
      setError(bulkError?.message || 'Failed to apply bulk updates');
    } finally {
      setIsApplyingBulkUpdate(false);
    }
  };

  const handleToggleArchived = () => {
    setShowArchived((prev) => !prev);
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
      item && item.name && (item.price !== null && item.price !== undefined) // Basic validation - allow price 0
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
        <div className="w-[55%] mb-6 flex flex-col items-center">
          <button
              onClick={() => document.getElementById('file-upload').click()}
              className="block w-full max-w-96 text-center bg-[#8DB670] rounded-xl pt-4 pb-4 font-semibold text-white mt-2 hover:bg-[#6c8b55] disabled:bg-gray-400"
            >
              Import Menu (PNG/JPEG/PDF)
            </button>
          <input id="file-upload" type="file" accept="image/png, image/jpeg, application/pdf" onChange={handleIngestFile} className="hidden"/>
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

      <div className="mt-10">
        <div className="flex flex-col gap-3 mb-4">
          <div className="flex flex-wrap items-center justify-between gap-3">
            <h2 className="text-2xl font-semibold">Existing Menu Items</h2>
            <div className="flex flex-wrap gap-2">
              <button
                onClick={handleToggleArchived}
                className="px-4 py-2 rounded-md border border-gray-300 bg-white hover:bg-gray-50"
              >
                {showArchived ? 'Hide Archived' : 'Show Archived'}
              </button>
              <button
                onClick={exportCsv}
                className="px-4 py-2 rounded-md bg-[#8DB670] text-white hover:bg-[#6c8b55]"
              >
                Export CSV
              </button>
            </div>
          </div>

          {selectedItemIds.length > 0 && (
            <div className="border border-[#8DB670] bg-green-50 rounded-xl p-4">
              <div className="flex flex-col gap-3">
                <div className="flex items-center justify-between gap-3">
                  <p className="font-medium">{selectedItemIds.length} item{selectedItemIds.length === 1 ? '' : 's'} selected</p>
                  <button
                    onClick={openBulkConfirmDialog}
                    className="px-4 py-2 rounded-md bg-[#8DB670] text-white hover:bg-[#6c8b55]"
                  >
                    Review Bulk Changes
                  </button>
                </div>

                <div className="grid gap-4 md:grid-cols-2">
                  <div>
                    <p className="font-medium mb-2">Add allergen tags</p>
                    <div className="flex flex-wrap gap-2">
                      {allergenOptions.map((option) => (
                        <button
                          key={`add-allergen-${option.id}`}
                          onClick={() => toggleBulkValue('addAllergens', option.id)}
                          className={`px-3 py-1 rounded-full border ${bulkDraft.addAllergens.includes(option.id) ? 'bg-[#8DB670] text-white border-[#8DB670]' : 'bg-white'}`}
                        >
                          {option.label}
                        </button>
                      ))}
                    </div>
                  </div>

                  <div>
                    <p className="font-medium mb-2">Remove allergen tags</p>
                    <div className="flex flex-wrap gap-2">
                      {allergenOptions.map((option) => (
                        <button
                          key={`remove-allergen-${option.id}`}
                          onClick={() => toggleBulkValue('removeAllergens', option.id)}
                          className={`px-3 py-1 rounded-full border ${bulkDraft.removeAllergens.includes(option.id) ? 'bg-red-600 text-white border-red-600' : 'bg-white'}`}
                        >
                          {option.label}
                        </button>
                      ))}
                    </div>
                  </div>

                  <div>
                    <p className="font-medium mb-2">Add dietary labels</p>
                    <div className="flex flex-wrap gap-2">
                      {dietaryCategories.map((option) => (
                        <button
                          key={`add-dietary-${option.id}`}
                          onClick={() => toggleBulkValue('addDietaryCategories', option.id)}
                          className={`px-3 py-1 rounded-full border ${bulkDraft.addDietaryCategories.includes(option.id) ? 'bg-[#8DB670] text-white border-[#8DB670]' : 'bg-white'}`}
                        >
                          {option.label}
                        </button>
                      ))}
                    </div>
                  </div>

                  <div>
                    <p className="font-medium mb-2">Remove dietary labels</p>
                    <div className="flex flex-wrap gap-2">
                      {dietaryCategories.map((option) => (
                        <button
                          key={`remove-dietary-${option.id}`}
                          onClick={() => toggleBulkValue('removeDietaryCategories', option.id)}
                          className={`px-3 py-1 rounded-full border ${bulkDraft.removeDietaryCategories.includes(option.id) ? 'bg-red-600 text-white border-red-600' : 'bg-white'}`}
                        >
                          {option.label}
                        </button>
                      ))}
                    </div>
                  </div>
                </div>
              </div>
            </div>
          )}

          <div className="space-y-3">
            {visibleMenuItems.length === 0 ? (
              <p className="text-gray-500">No menu items found.</p>
            ) : (
              visibleMenuItems.map((item) => (
                <div key={item.id} className="border rounded-xl p-4 bg-white shadow-sm">
                  <div className="flex flex-col md:flex-row md:items-start md:justify-between gap-4">
                    <div className="flex items-start gap-3">
                      <input
                        type="checkbox"
                        checked={selectedItemIds.includes(item.id)}
                        onChange={() => toggleSelectedItem(item.id)}
                        className="mt-1 h-4 w-4"
                      />
                      <div>
                        <div className="flex items-center gap-2 flex-wrap">
                          <h3 className="text-lg font-semibold">{item.name}</h3>
                          {item.archived && (
                            <span className="text-xs px-2 py-1 rounded-full bg-gray-200 text-gray-700">Archived</span>
                          )}
                        </div>
                        <p className="text-sm text-gray-600">{item.description}</p>
                        <p className="text-sm text-gray-800 font-medium mt-1">
                          ${typeof item.price === 'number' ? item.price.toFixed(2) : String(item.price || '0.00')}
                        </p>
                        {item.ingredients && (
                          <p className="text-sm text-gray-600 mt-1"><span className="font-medium">Ingredients:</span> {item.ingredients}</p>
                        )}
                        <p className="text-sm text-gray-600 mt-1">
                          <span className="font-medium">Allergens:</span> {(item.allergens || []).join(', ') || 'None'}
                        </p>
                        <p className="text-sm text-gray-600">
                          <span className="font-medium">Dietary:</span> {(item.dietaryCategories || []).join(', ') || 'None'}
                        </p>
                      </div>
                    </div>

                    <div className="flex flex-wrap gap-2">
                      <button
                        onClick={() => duplicateMenuItem(item.id)}
                        className="px-3 py-2 rounded-md border border-gray-300 bg-white hover:bg-gray-50"
                      >
                        Duplicate
                      </button>
                      <button
                        onClick={() => toggleArchiveMenuItem(item)}
                        className="px-3 py-2 rounded-md text-white bg-gray-700 hover:bg-gray-800"
                      >
                        {item.archived ? 'Restore' : 'Archive'}
                      </button>
                    </div>
                  </div>
                </div>
              ))
            )}
          </div>
        </div>
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
          <div className='clear-right flex flex-col justify-center items-center gap-6 mt-10'>
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

      {showBulkConfirmDialog && (
        <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50">
          <div className="bg-white rounded-lg p-6 max-w-2xl w-full">
            <h3 className="text-lg font-medium text-gray-900 mb-4">Confirm Bulk Update</h3>
            <p className="text-gray-600 mb-4">
              You are about to update {bulkSummary.count} selected item{bulkSummary.count === 1 ? '' : 's'}.
            </p>
            <div className="space-y-2 text-sm text-gray-700 mb-6">
              <p><span className="font-medium">Add allergens:</span> {bulkSummary.addAllergens.join(', ') || 'None'}</p>
              <p><span className="font-medium">Remove allergens:</span> {bulkSummary.removeAllergens.join(', ') || 'None'}</p>
              <p><span className="font-medium">Add dietary labels:</span> {bulkSummary.addDietaryCategories.join(', ') || 'None'}</p>
              <p><span className="font-medium">Remove dietary labels:</span> {bulkSummary.removeDietaryCategories.join(', ') || 'None'}</p>
            </div>
            <div className="flex justify-end space-x-3">
              <button
                onClick={() => setShowBulkConfirmDialog(false)}
                className="px-4 py-2 border border-gray-300 rounded-md shadow-sm text-sm font-medium text-gray-700 bg-white hover:bg-gray-50"
              >
                Cancel
              </button>
              <button
                onClick={applyBulkUpdate}
                disabled={isApplyingBulkUpdate}
                className="px-4 py-2 rounded-md shadow-sm text-sm font-medium text-white bg-[#8DB670] hover:bg-[#6c8b55] disabled:bg-gray-400"
              >
                {isApplyingBulkUpdate ? 'Applying...' : 'Apply Changes'}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};

export default ManageMenuItems;