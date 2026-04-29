import React, { useState, useEffect } from 'react';
import { useParams, useNavigate, Link } from 'react-router-dom';
import { Capacitor } from '@capacitor/core';
import { Toast } from '@capacitor/toast';
import { api } from '../../services/api';
import MenuItemForm from '../Menu/MenuItemForm';

const allergenOptions = [
  { id: 'milk', label: 'Milk', icon: '🥛' },
  { id: 'eggs', label: 'Eggs', icon: '🥚' },
  { id: 'fish', label: 'Fish', icon: '🐟' },
  { id: 'tree_nuts', label: 'Tree Nuts', icon: '🌰' },
  { id: 'wheat', label: 'Wheat', icon: '🌾' },
  { id: 'crustaceans', label: 'Crustaceans', icon: '🦀' },
  { id: 'gluten_free', label: 'Gluten-Free', icon: '🌾' },
  { id: 'peanuts', label: 'Peanuts', icon: '🥜' },
  { id: 'soybeans', label: 'Soybeans', icon: '🫘' },
  { id: 'sesame', label: 'Sesame', icon: '✨' }
];

const dietaryCategories = [
  { id: 'vegan', label: 'Vegan', icon: '🌱' },
  { id: 'vegetarian', label: 'Vegetarian', icon: '🥗' }
];

// Add CSS for animations
const styles = `
  @keyframes fadeIn {
    from { opacity: 0; }
    to { opacity: 1; }
  }
  
  .animate-fadeIn {
    animation: fadeIn 0.3s ease-in-out;
  }
`;

const RestaurantPage = () => {
  const { restaurantId } = useParams();
  const navigate = useNavigate();
  const [restaurant, setRestaurant] = useState(null);
  const [menuItems, setMenuItems] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [editingItemId, setEditingItemId] = useState(null);
  const [originalItem, setOriginalItem] = useState(null);
  const [restaurantRole, setRestaurantRole] = useState(null); // 'manager' | 'staff' for this restaurant
  
  // Add state for restaurant editing
  const [editingRestaurant, setEditingRestaurant] = useState(false);
  const [restaurantFormData, setRestaurantFormData] = useState({
    name: '',
    address: '',
    phone: '',
    cuisine_type: ''
  });
  
  // Team (manager only): members list, invite form
  const [members, setMembers] = useState([]);
  const [membersLoading, setMembersLoading] = useState(false);
  const [inviteEmail, setInviteEmail] = useState('');
  const [inviteRole, setInviteRole] = useState('staff');
  const [inviteError, setInviteError] = useState('');
  const [inviteSuccess, setInviteSuccess] = useState('');
  
  // Add state for confirmation dialog and success messages
  const [showConfirmDialog, setShowConfirmDialog] = useState(false);
  const [itemToDelete, setItemToDelete] = useState(null);
  const [showSuccessMessage, setShowSuccessMessage] = useState(false);
  const [successMessage, setSuccessMessage] = useState('');
  const [showDeleteSuccessMessage, setShowDeleteSuccessMessage] = useState(false);
  const [deleteSuccessMessage, setDeleteSuccessMessage] = useState('');
  const [showItemsAddedMessage, setShowItemsAddedMessage] = useState(false);
  const [itemsAddedMessage, setItemsAddedMessage] = useState('');
  const [showDeleteRestaurantDialog, setShowDeleteRestaurantDialog] = useState(false);

  const showToast = async (message) => {
    if (Capacitor.isNativePlatform()) {
      await Toast.show({ text: message, duration: 'short', position: 'bottom' });
    } else {
      // Instead of using alert, we'll show our styled popup
      setDeleteSuccessMessage(message);
      setShowDeleteSuccessMessage(true);
      
      // Auto-hide after 3 seconds
      setTimeout(() => {
        setShowDeleteSuccessMessage(false);
      }, 3000);
    }
  };

  const fetchRestaurantData = async () => {
    try {
      const user = await api.getCurrentUser();
      const role = user?.restaurants?.find(r => String(r.id) === String(restaurantId))?.role;
      setRestaurantRole(role || null);
      if (role) api.setCurrentRestaurant(restaurantId, role);

      const restaurantData = await api.getRestaurants();
      const restaurant = restaurantData.find(r => String(r.id) === restaurantId);

      if (!restaurant) {
        setError('Restaurant not found');
        await showToast('Restaurant not found');
        return;
      }

      setRestaurant(restaurant);
      
      setRestaurantFormData({
        name: restaurant.name || '',
        address: restaurant.address || '',
        phone: restaurant.phone || '',
        cuisine_type: restaurant.cuisine_type || ''
      });

      const menuData = await api.getMenuItems(restaurantId);
      setMenuItems(menuData);

      if (role === 'manager') {
        setMembersLoading(true);
        try {
          const memberList = await api.getRestaurantMembers(restaurantId);
          setMembers(memberList);
        } catch {
          setMembers([]);
        } finally {
          setMembersLoading(false);
        }
      }
    } catch (err) {
      setError('Failed to load restaurant information');
      await showToast('Failed to load restaurant information');
    } finally {
      setLoading(false);
    }
  };

  // Main effect for loading restaurant data
  useEffect(() => {
    fetchRestaurantData();
  }, [restaurantId]);

  // Separate useEffect for handling success messages from localStorage
  useEffect(() => {
    // Check for success message from localStorage after component mounts
    if (localStorage.getItem('menuItemsAdded') === 'true') {
      const count = localStorage.getItem('menuItemsAddedCount') || '0';
      setItemsAddedMessage(`${count} menu item${count !== '1' ? 's' : ''} added successfully!`);
      setShowItemsAddedMessage(true);
      
      // Clear localStorage
      localStorage.removeItem('menuItemsAdded');
      localStorage.removeItem('menuItemsAddedCount');
      
      // Auto-hide success message after 3 seconds
      setTimeout(() => {
        setShowItemsAddedMessage(false);
      }, 3000);
    }
  }, []);

  // Restaurant editing functions
  const handleEditRestaurant = () => {
    setEditingRestaurant(true);
  };

  const handleCancelEditRestaurant = () => {
    setEditingRestaurant(false);
    // Reset form data to current restaurant values
    setRestaurantFormData({
      name: restaurant.name || '',
      address: restaurant.address || '',
      phone: restaurant.phone || '',
      cuisine_type: restaurant.cuisine_type || ''
    });
  };

  const handleRestaurantInputChange = (e) => {
    const { name, value } = e.target;
    setRestaurantFormData({
      ...restaurantFormData,
      [name]: value
    });
  };

  const handleSaveRestaurant = async () => {
    try {
      await api.updateRestaurant(restaurantId, restaurantFormData);
      
      // Update local state
      setRestaurant({
        ...restaurant,
        ...restaurantFormData
      });
      
      // Exit edit mode
      setEditingRestaurant(false);
      
      // Show success message
      setSuccessMessage('Restaurant information updated successfully');
      setShowSuccessMessage(true);
      
      // Auto-hide success message after 3 seconds
      setTimeout(() => {
        setShowSuccessMessage(false);
      }, 3000);
    } catch (error) {
      await showToast('Failed to update restaurant information');
      console.error('Restaurant update error:', error);
    }
  };

  // Menu item functions
  const confirmDelete = (menuItemId) => {
    const itemToDelete = menuItems.find(item => item.id === menuItemId);
    if (!itemToDelete) return;
    
    setItemToDelete(itemToDelete);
    setShowConfirmDialog(true);
  };
  
  const cancelDeletion = () => {
    setShowConfirmDialog(false);
    setItemToDelete(null);
  };
  
  const handleDelete = async () => {
    if (!itemToDelete) return;
    
    try {
      await api.deleteMenuItem(restaurantId, itemToDelete.id);
      
      // Instead of showing a toast, show the styled success dialog
      setDeleteSuccessMessage(`${itemToDelete.name} deleted successfully`);
      setShowDeleteSuccessMessage(true);
      
      // Update the UI by removing the deleted item
      setMenuItems(menuItems.filter(item => item.id !== itemToDelete.id));
      
      // Close the confirmation dialog
      setShowConfirmDialog(false);
      setItemToDelete(null);
      
      // Auto-hide success message after 3 seconds
      setTimeout(() => {
        setShowDeleteSuccessMessage(false);
      }, 3000);
    } catch (error) {
      await showToast('Failed to delete menu item');
      console.error('Delete error:', error);
      
      // Close the dialog even on error
      setShowConfirmDialog(false);
      setItemToDelete(null);
    }
  };

  const cancelDeleteRestaurant = () => setShowDeleteRestaurantDialog(false);

  const handleDeleteRestaurant = async () => {
    try {
      await api.deleteRestaurant(restaurantId);
      setShowDeleteRestaurantDialog(false);
      navigate('/dashboard');
    } catch (error) {
      await showToast(error.message || 'Failed to delete restaurant');
      setShowDeleteRestaurantDialog(false);
    }
  };

  const handleEdit = (menuItemId) => {
    // Store the original item before starting to edit
    const itemToEdit = menuItems.find(item => item.id === menuItemId);
    setOriginalItem(itemToEdit);
  
    // Toggle editing state for this item
    setEditingItemId(editingItemId === menuItemId ? null : menuItemId);
  };

  const handleCancelEdit = () => {
    // If we have the original item, replace the current edited item with it
    if (originalItem) {
      setMenuItems(menuItems.map(item => 
        item.id === originalItem.id ? originalItem : item
      ));
    }
  
    // Reset editing state
    setEditingItemId(null);
    setOriginalItem(null);
  };

  const handleSaveEdit = async (updatedItem) => {
    try {
      // Send the updated item to the API
      await api.updateMenuItem(restaurantId, updatedItem.id, updatedItem);
      
      // Update the local items list
      setMenuItems(menuItems.map(item => 
        item.id === updatedItem.id ? updatedItem : item
      ));
      
      // Exit edit mode
      setEditingItemId(null);
      
      // Show custom success message
      setSuccessMessage(`${updatedItem.name} updated successfully`);
      setShowSuccessMessage(true);
      
      // Hide success message after 3 seconds
      setTimeout(() => {
        setShowSuccessMessage(false);
      }, 3000);
    } catch (error) {
      await showToast('Failed to update menu item');
      console.error('Update error:', error);
    }
  };

  const handleFormChange = (updatedData) => {
    // Find the item being edited
    const itemIndex = menuItems.findIndex(item => item.id === editingItemId);
    if (itemIndex === -1) return;

    // Create a new array with the updated item
    const updatedItems = [...menuItems];
    updatedItems[itemIndex] = {
      ...updatedItems[itemIndex],
      ...updatedData
    };

    // Update state
    setMenuItems(updatedItems);
  };

  if (loading) {
    return (
      <div className="max-w-4xl mx-auto p-6 font-[Roboto_Flex]">
        <div className="flex justify-center items-center h-64">
          <div className="animate-spin rounded-full h-10 w-10 border-t-2 border-b-2 border-[#8DB670]"></div>
        </div>
      </div>
    );
  }

  if (error) {
    return (
      <div className="max-w-4xl mx-auto p-6 font-[Roboto_Flex]">
        <div className="bg-red-100 border border-red-400 text-red-700 px-4 py-3 rounded-xl mb-4">
          {error}
        </div>
      </div>
    );
  }

  return (
    <div className="max-w-4xl mx-auto p-6 flex flex-col justify-center items-center font-[Roboto_Flex]">
      <style>{styles}</style>

      <div className="w-full mb-4">
        <Link to="/dashboard" className="text-sm text-[#8DB670] hover:underline">
          ← My restaurants
        </Link>
      </div>

      {/* Restaurant Information Section */}
      <div className="w-full bg-white rounded-xl shadow-md p-6 mb-8">
        {restaurantRole === 'staff' && (
          <p className="text-sm text-gray-500 mb-2">You have staff access: you can edit menu items but not restaurant settings.</p>
        )}
        {editingRestaurant ? (
          <div className="animate-fadeIn">
            <h2 className="text-2xl font-bold mb-4">Edit Restaurant Information</h2>
            
            <div className="grid grid-cols-1 md:grid-cols-2 gap-4 mb-6">
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">Restaurant Name</label>
                <input
                  type="text"
                  name="name"
                  value={restaurantFormData.name}
                  onChange={handleRestaurantInputChange}
                  className="w-full p-2 border border-gray-300 rounded-lg focus:ring-[#8DB670] focus:border-[#8DB670]"
                  required
                />
              </div>
              
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">Cuisine Type</label>
                <input
                  type="text"
                  name="cuisine_type"
                  value={restaurantFormData.cuisine_type}
                  onChange={handleRestaurantInputChange}
                  className="w-full p-2 border border-gray-300 rounded-lg focus:ring-[#8DB670] focus:border-[#8DB670]"
                />
              </div>
              
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">Phone</label>
                <input
                  type="text"
                  name="phone"
                  value={restaurantFormData.phone}
                  onChange={handleRestaurantInputChange}
                  className="w-full p-2 border border-gray-300 rounded-lg focus:ring-[#8DB670] focus:border-[#8DB670]"
                />
              </div>
              
              <div className="md:col-span-2">
                <label className="block text-sm font-medium text-gray-700 mb-1">Address</label>
                <input
                  type="text"
                  name="address"
                  value={restaurantFormData.address}
                  onChange={handleRestaurantInputChange}
                  className="w-full p-2 border border-gray-300 rounded-lg focus:ring-[#8DB670] focus:border-[#8DB670]"
                />
              </div>
            </div>
            
            <div className="flex justify-end space-x-3">
              <button
                onClick={handleCancelEditRestaurant}
                className="px-4 py-2 border border-gray-300 rounded-xl shadow-sm text-sm font-medium text-gray-700 bg-white hover:bg-gray-50"
              >
                Cancel
              </button>
              <button
                onClick={handleSaveRestaurant}
                className="px-4 py-2 rounded-xl shadow-sm text-sm font-medium text-white bg-[#8DB670] hover:bg-[#6c8b55]"
              >
                Save Changes
              </button>
            </div>
          </div>
        ) : (
          <div className="relative">
            {/* Edit button: manager only */}
            {restaurantRole === 'manager' && (
              <button
                onClick={handleEditRestaurant}
                className="absolute top-0 right-0 bg-blue-500 text-white p-1.5 rounded-lg hover:bg-blue-600 transition"
                title="Edit Restaurant Information"
              >
                <svg xmlns="http://www.w3.org/2000/svg" className="h-4 w-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15.232 5.232l3.536 3.536m-2.036-5.036a2.5 2.5 0 113.536 3.536L6.5 21.036H3v-3.572L16.732 3.732z" />
                </svg>
              </button>
            )}
            
            <h2 className="text-2xl font-bold mb-2">{restaurant.name}</h2>
            <p className="text-sm text-gray-600 mb-4">
              New to SafeEats?{" "}
              <a
                href="/owners-quick-start.html"
                target="_blank"
                rel="noreferrer"
                className="text-[#0ea5e9] hover:underline font-medium"
              >
                Open the Owner Quick-Start guide
              </a>
              {" "}for a short walkthrough.
            </p>
            
            <div className="grid grid-cols-1 md:grid-cols-2 gap-2 text-sm text-gray-600">
              <div>
                <p className="font-medium">Cuisine:</p>
                <p>{restaurant.cuisine_type || 'Not specified'}</p>
              </div>
              
              <div>
                <p className="font-medium">Phone:</p>
                <p>{restaurant.phone || 'Not specified'}</p>
              </div>
              
              <div className="md:col-span-2">
                <p className="font-medium">Address:</p>
                <p>{restaurant.address || 'Not specified'}</p>
              </div>
            </div>
          </div>
        )}
      </div>

      {/* Team section: manager only */}
      {restaurantRole === 'manager' && (
        <div className="w-full bg-white rounded-xl shadow-md p-6 mb-8">
          <h3 className="text-xl font-semibold mb-4">Team</h3>
          {membersLoading ? (
            <p className="text-gray-500">Loading members…</p>
          ) : (
            <>
              <ul className="space-y-2 mb-4">
                {members.map((m) => (
                  <li key={m.uid} className="flex items-center justify-between py-2 border-b border-gray-100">
                    <span className="text-gray-700">{m.email}</span>
                    <span className="flex items-center gap-2">
                      <span className="text-xs px-2 py-0.5 rounded bg-gray-100 text-gray-600">{m.role}</span>
                      {m.is_owner && <span className="text-xs text-gray-400">(owner)</span>}
                      {!m.is_owner && (
                        <button
                          type="button"
                          onClick={async () => {
                            if (!window.confirm(`Remove ${m.email} from this restaurant?`)) return;
                            try {
                              await api.removeRestaurantMember(restaurantId, m.uid);
                              setMembers(members.filter(x => x.uid !== m.uid));
                              await showToast('Member removed');
                            } catch (err) {
                              await showToast(err.message || 'Failed to remove');
                            }
                          }}
                          className="text-red-600 hover:underline text-sm"
                        >
                          Remove
                        </button>
                      )}
                    </span>
                  </li>
                ))}
              </ul>
              <div className="flex flex-wrap items-end gap-2">
                <input
                  type="email"
                  placeholder="Email to invite"
                  value={inviteEmail}
                  onChange={(e) => { setInviteEmail(e.target.value); setInviteError(''); setInviteSuccess(''); }}
                  className="border border-gray-300 rounded-lg px-3 py-2 flex-1 min-w-[180px]"
                />
                <select
                  value={inviteRole}
                  onChange={(e) => setInviteRole(e.target.value)}
                  className="border border-gray-300 rounded-lg px-3 py-2"
                >
                  <option value="staff">Staff</option>
                  <option value="manager">Manager</option>
                </select>
                <button
                  type="button"
                  onClick={async () => {
                    if (!inviteEmail.trim()) return;
                    setInviteError('');
                    setInviteSuccess('');
                    try {
                      await api.inviteRestaurantMember(restaurantId, inviteEmail.trim(), inviteRole);
                      setInviteEmail('');
                      setInviteSuccess(`${inviteEmail} added as ${inviteRole}`);
                      const memberList = await api.getRestaurantMembers(restaurantId);
                      setMembers(memberList);
                    } catch (err) {
                      setInviteError(err.message || 'Invite failed');
                    }
                  }}
                  className="bg-[#8DB670] text-white px-4 py-2 rounded-lg hover:bg-[#6c8b55]"
                >
                  Invite
                </button>
              </div>
              {inviteError && <p className="text-red-600 text-sm mt-2">{inviteError}</p>}
              {inviteSuccess && <p className="text-green-600 text-sm mt-2">{inviteSuccess}</p>}
            </>
          )}
        </div>
      )}

      {/* Menu Items Section */}
      <div className="w-full bg-white rounded-xl shadow-md p-6 mb-6">
        <div className="flex flex-col md:flex-row md:items-center md:justify-between mb-6 gap-2">
          <h3 className="text-2xl font-semibold text-center md:text-left">Menu Items</h3>
          <a
            href="/how-to-add-menu-items.html"
            target="_blank"
            rel="noreferrer"
            className="text-sm text-[#0ea5e9] hover:underline text-center md:text-right"
          >
            Need help adding items? Open “How Do I Add Menu Items?”
          </a>
        </div>
        {menuItems.length === 0 ? (
          <div className="text-center py-8">
            <p className="text-gray-500 mb-4">No menu items added yet.</p>
            <p className="text-gray-500 mb-6">Add your first items to start building your menu!</p>
          </div>
        ) : (
          <ul className="space-y-4 w-full">
            {menuItems.map((item, index) => (
              <li key={item.id} className="border rounded-xl p-4 shadow-sm relative">
                {editingItemId === item.id ? (
                  <div className="animate-fadeIn">
                    <MenuItemForm 
                      formIndex={index}
                      onRemove={() => confirmDelete(item.id)}
                      onFormChange={handleFormChange}
                      initialData={{
                        ...item,
                        // Store both numeric and formatted values
                        priceNumeric: typeof item.price === 'string' && item.price.includes('$') 
                                    ? parseFloat(item.price.replace(/[^\d.]/g, ''))
                                    : typeof item.price === 'number'
                                      ? item.price
                                      : 0,
                        price: typeof item.price === 'string' && item.price.includes('$')
                              ? item.price
                              : typeof item.price === 'number'
                                ? `$${item.price.toFixed(2)}`
                                : '$0.00'
                      }}
                      onImageChange={(newUrl) => {
                        setMenuItems((prev) =>
                          prev.map((i) =>
                            i.id === item.id ? { ...i, image_url: newUrl } : i
                          )
                        );
                      }}
                    />
                    <div className="flex justify-end space-x-2 mt-4">
                      <button
                        onClick={handleCancelEdit}
                        className="bg-gray-500 hover:bg-gray-600 text-white py-2 px-4 rounded-xl transition"
                      >
                        Cancel
                      </button>
                      <button
                        onClick={() => handleSaveEdit(menuItems.find(i => i.id === editingItemId))}
                        className="bg-[#8DB670] hover:bg-[#6c8b55] text-white py-2 px-4 rounded-xl transition"
                      >
                        Save Changes
                      </button>
                    </div>
                  </div>
                ) : (
                  // Show compact view when not editing
                  <div>
                    {/* Edit and Delete buttons in top right corner - Changed edit from amber to blue */}
                    <div className="absolute top-3 right-3 flex space-x-2">
                      <button
                        onClick={() => handleEdit(item.id)}
                        className="bg-blue-500 text-white p-1.5 rounded-lg hover:bg-blue-600 transition"
                        title="Edit Item"
                      >
                        <svg xmlns="http://www.w3.org/2000/svg" className="h-4 w-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15.232 5.232l3.536 3.536m-2.036-5.036a2.5 2.5 0 113.536 3.536L6.5 21.036H3v-3.572L16.732 3.732z" />
                        </svg>
                      </button>
                      <button
                        onClick={() => confirmDelete(item.id)}
                        className="bg-red-500 text-white p-1.5 rounded-lg hover:bg-red-600 transition"
                        title="Delete Item"
                      >
                        <svg xmlns="http://www.w3.org/2000/svg" className="h-4 w-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
                        </svg>
                      </button>
                    </div>
                    
                    <div className="pr-16">
                      {item.image_url && (
                        <img
                          src={item.image_url}
                          alt={item.name}
                          className="w-24 h-24 object-cover rounded-md mb-2 shadow-sm"
                        />
                      )}
                      <p className="text-lg font-medium">{item.name}</p>
                      {/* Changed from green to bold dark gray for prices */}
                      <p className="text-gray-800 font-semibold">
                        ${typeof item.price === 'number' ? item.price.toFixed(2) : 
                          typeof item.price === 'string' && item.price.includes('$') ? 
                          item.price.replace('$', '') : item.price}
                      </p>
                      
                      {/* Display allergens with tooltips */}
                      {item.allergens && item.allergens.length > 0 && (
                        <div className="mt-1 text-sm">
                          <span className="text-gray-700">Allergens: </span>
                          {item.allergens.map(id => {
                            const allergenOption = allergenOptions.find(a => a.id === id);
                            return allergenOption ? (
                              <span 
                                key={id} 
                                className="mr-1 relative group cursor-pointer"
                              >
                                <span>{allergenOption.icon}</span>
                                <span className="absolute bottom-full mb-1 left-1/2 transform -translate-x-1/2 bg-white border border-gray-200 shadow-lg text-gray-800 text-xs rounded-md py-1 px-2 opacity-0 group-hover:opacity-100 transition-opacity duration-200 pointer-events-none whitespace-nowrap z-10">
                                  {allergenOption.label}
                                </span>
                              </span>
                            ) : null;
                          })}
                        </div>
                      )}
                      
                      {/* Display dietary categories with tooltips */}
                      {item.dietaryCategories && item.dietaryCategories.length > 0 && (
                        <div className="mt-1 text-sm">
                          <span className="text-gray-700">Dietary: </span>
                          {item.dietaryCategories.map(id => {
                            const dietaryOption = dietaryCategories.find(d => d.id === id);
                            return dietaryOption ? (
                              <span 
                                key={id} 
                                className="mr-1 relative group cursor-pointer"
                              >
                                <span>{dietaryOption.icon}</span>
                                <span className="absolute bottom-full mb-1 left-1/2 transform -translate-x-1/2 bg-white border border-gray-200 shadow-lg text-gray-800 text-xs rounded-md py-1 px-2 opacity-0 group-hover:opacity-100 transition-opacity duration-200 pointer-events-none whitespace-nowrap z-10">
                                  {dietaryOption.label}
                                </span>
                              </span>
                            ) : null;
                          })}
                        </div>
                      )}
                    </div>
                  </div>
                )}
              </li>
            ))}
          </ul>
        )}
      </div>

      {restaurant &&
        String(restaurant.owner_uid || '') === String(localStorage.getItem('user_id') || '') && (
          <div className="w-full max-w-4xl mb-8 border border-red-200 bg-red-50 rounded-xl p-6">
            <h3 className="text-lg font-semibold text-red-900 mb-2">Delete restaurant</h3>
            <p className="text-sm text-red-800 mb-4">
              Permanently remove this restaurant, all of its menu items, and team memberships. This cannot be undone.
            </p>
            <button
              type="button"
              onClick={() => setShowDeleteRestaurantDialog(true)}
              className="px-4 py-2 rounded-xl text-sm font-medium text-white bg-red-600 hover:bg-red-700"
            >
              Delete this restaurant…
            </button>
          </div>
        )}
      
      <button 
        onClick={() => navigate(`/restaurant/${restaurantId}/menu`)}
        className="mx-auto w-full max-w-72 text-center bg-[#8DB670] rounded-xl pt-4 pb-4 font-semibold text-white mt-6 hover:bg-[#6c8b55] transition"
      >
        Create New Items
      </button>
      
      {/* Confirmation Dialog for Delete */}
      {showConfirmDialog && itemToDelete && (
        <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50 animate-fadeIn">
          <div className="bg-white rounded-lg p-6 max-w-md w-full">
            <h3 className="text-lg font-medium text-gray-900 mb-4">Confirm Deletion</h3>
            <p className="text-gray-600 mb-6">
              Are you sure you want to delete "<span className="font-semibold">{itemToDelete.name}</span>"? This action cannot be undone.
            </p>
            <div className="flex justify-end space-x-3">
              <button
                onClick={cancelDeletion}
                className="px-4 py-2 border border-gray-300 rounded-md shadow-sm text-sm font-medium text-gray-700 bg-white hover:bg-gray-50"
              >
                Cancel
              </button>
              <button
                onClick={handleDelete}
                className="px-4 py-2 rounded-md shadow-sm text-sm font-medium text-white bg-red-600 hover:bg-red-700"
              >
                Yes, Delete
              </button>
            </div>
          </div>
        </div>
      )}

      {showDeleteRestaurantDialog && (
        <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50 animate-fadeIn">
          <div className="bg-white rounded-lg p-6 max-w-md w-full">
            <h3 className="text-lg font-medium text-gray-900 mb-4">Delete restaurant</h3>
            <p className="text-gray-600 mb-6">
              Delete <span className="font-semibold">{restaurant?.name}</span> and all menu data? This cannot be undone.
            </p>
            <div className="flex justify-end space-x-3">
              <button
                type="button"
                onClick={cancelDeleteRestaurant}
                className="px-4 py-2 border border-gray-300 rounded-md shadow-sm text-sm font-medium text-gray-700 bg-white hover:bg-gray-50"
              >
                Cancel
              </button>
              <button
                type="button"
                onClick={handleDeleteRestaurant}
                className="px-4 py-2 rounded-md shadow-sm text-sm font-medium text-white bg-red-600 hover:bg-red-700"
              >
                Yes, delete restaurant
              </button>
            </div>
          </div>
        </div>
      )}
      
      {/* Success Message */}
      {showSuccessMessage && (
        <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50 animate-fadeIn">
          <div className="bg-white rounded-lg p-6 max-w-md w-full">
            <div className="flex items-center mb-4">
              <svg className="w-6 h-6 text-green-500 mr-2" fill="none" stroke="currentColor" viewBox="0 0 24 24" xmlns="http://www.w3.org/2000/svg">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M5 13l4 4L19 7"></path>
              </svg>
              <h3 className="text-lg font-medium text-gray-900">Success</h3>
            </div>
            <p className="text-gray-600 mb-6">{successMessage}</p>
            <div className="flex justify-end">
              <button
                onClick={() => setShowSuccessMessage(false)}
                className="px-4 py-2 rounded-md shadow-sm text-sm font-medium text-white bg-green-600 hover:bg-green-700"
              >
                OK
              </button>
            </div>
          </div>
        </div>
      )}
      
      {/* Success Message for Deletions */}
      {showDeleteSuccessMessage && (
        <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50 animate-fadeIn">
          <div className="bg-white rounded-lg p-6 max-w-md w-full">
            <div className="flex items-center mb-4">
              <svg className="w-6 h-6 text-green-500 mr-2" fill="none" stroke="currentColor" viewBox="0 0 24 24" xmlns="http://www.w3.org/2000/svg">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M5 13l4 4L19 7"></path>
              </svg>
              <h3 className="text-lg font-medium text-gray-900">Success</h3>
            </div>
            <p className="text-gray-600 mb-6">{deleteSuccessMessage}</p>
            <div className="flex justify-end">
              <button
                onClick={() => setShowDeleteSuccessMessage(false)}
                className="px-4 py-2 rounded-md shadow-sm text-sm font-medium text-white bg-green-600 hover:bg-green-700"
              >
                OK
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Success Message for Items Added */}
      {showItemsAddedMessage && (
        <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50 animate-fadeIn">
          <div className="bg-white rounded-lg p-6 max-w-md w-full">
            <div className="flex items-center mb-4">
              <svg className="w-6 h-6 text-green-500 mr-2" fill="none" stroke="currentColor" viewBox="0 0 24 24" xmlns="http://www.w3.org/2000/svg">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M5 13l4 4L19 7"></path>
              </svg>
              <h3 className="text-lg font-medium text-gray-900">Success</h3>
            </div>
            <p className="text-gray-600 mb-6">{itemsAddedMessage}</p>
            <div className="flex justify-end">
              <button
                onClick={() => setShowItemsAddedMessage(false)}
                className="px-4 py-2 rounded-md shadow-sm text-sm font-medium text-white bg-green-600 hover:bg-green-700"
              >
                OK
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};

export default RestaurantPage;