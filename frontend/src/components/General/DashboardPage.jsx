import React, { useState, useEffect, useCallback } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import { api } from '../../services/api';

const DashboardPage = () => {
  const navigate = useNavigate();
  const [loading, setLoading] = useState(true);
  const [user, setUser] = useState(null);
  const [restaurants, setRestaurants] = useState([]);
  const [error, setError] = useState('');

  const load = useCallback(async () => {
    setError('');
    setLoading(true);
    try {
      const u = await api.getCurrentUser();
      if (!u) {
        navigate('/', { replace: true });
        return;
      }
      if (u.is_admin) {
        navigate('/restaurant-list', { replace: true });
        return;
      }
      setUser(u);
      const list = Array.isArray(u.restaurants) ? u.restaurants : api.getRestaurantsList();
      setRestaurants(list);
    } catch (e) {
      setError(e.message || 'Failed to load your restaurants');
    } finally {
      setLoading(false);
    }
  }, [navigate]);

  useEffect(() => {
    const token = localStorage.getItem('auth_token');
    if (!token) {
      navigate('/', { replace: true });
      return;
    }
    load();
  }, [load, navigate]);

  const roleLabel = (r) => {
    if (r.is_owner) return 'Owner';
    if (r.role === 'manager') return 'Team · Manager';
    if (r.role === 'staff') return 'Team · Staff';
    return r.role || 'Member';
  };

  if (loading) {
    return (
      <div className="container mx-auto px-4 py-10 font-[Roboto_Flex]">
        <p className="text-center text-gray-500">Loading your restaurants…</p>
      </div>
    );
  }

  return (
    <div className="container mx-auto px-4 py-8 max-w-3xl font-[Roboto_Flex]">
      <h1 className="text-3xl font-bold text-center mb-2">My restaurants</h1>
      <p className="text-center text-gray-600 mb-8">
        Places you own or were invited to. Refresh the page after a manager adds you to see updates.
      </p>

      {error && (
        <div className="bg-red-50 border border-red-200 text-red-800 px-4 py-3 rounded mb-4">{error}</div>
      )}

      <div className="flex flex-col sm:flex-row gap-3 justify-center mb-8">
        <Link
          to="/add-restaurant"
          className="inline-block text-center bg-[#8DB670] text-white font-semibold rounded-xl py-3 px-6 hover:bg-[#6c8b55]"
        >
          Register a new restaurant
        </Link>
        <button
          type="button"
          onClick={() => load()}
          className="inline-block text-center border border-gray-300 rounded-xl py-3 px-6 hover:bg-gray-50"
        >
          Refresh list
        </button>
      </div>

      {restaurants.length === 0 ? (
        <div className="bg-white rounded-xl shadow p-8 text-center text-gray-600">
          <p className="mb-2">You are not linked to any restaurant yet.</p>
          <p className="text-sm mb-4">
            Ask an owner or manager to invite your account email, or register a restaurant you manage.
          </p>
        </div>
      ) : (
        <ul className="space-y-4">
          {restaurants.map((r) => (
            <li key={r.id} className="bg-white rounded-xl shadow p-5 flex flex-col sm:flex-row sm:items-center sm:justify-between gap-3">
              <div>
                <p className="font-semibold text-lg text-gray-900">{r.name || 'Unnamed restaurant'}</p>
                <p className="text-sm text-gray-500 mt-1">{roleLabel(r)}</p>
              </div>
              <Link
                to={`/restaurant/${r.id}`}
                onClick={() => api.setCurrentRestaurant(r.id, r.role)}
                className="shrink-0 text-center bg-[#8DB670] text-white font-semibold rounded-xl py-2 px-5 hover:bg-[#6c8b55]"
              >
                Open
              </Link>
            </li>
          ))}
        </ul>
      )}

      {user?.email && (
        <p className="text-center text-sm text-gray-400 mt-10">Signed in as {user.email}</p>
      )}
    </div>
  );
};

export default DashboardPage;
