
// __mocks__/api.js
export const api = {
  parseIngredientsWithAI: jest.fn(async (text) => {
    return {
      allergens: ["milk"],
      dietaryCategories: ["vegetarian"],
      extractedIngredients: ["milk", "eggs", "flour"]
    };
  }),
  ingestMenuImage: jest.fn(async (file) => ({
    items: [
      { name: "Caprese Salad", description: "Tomato basil mozzarella", price: 1099, allergens: ["milk"], dietaryCategories: ["vegetarian"], ingredients: "tomato, basil, mozzarella" },
      { name: "Pesto Pasta", description: "Pine nuts + parm", price: 1599, allergens: ["milk", "tree_nuts"], dietaryCategories: ["vegetarian"], ingredients: "pasta, pesto" }
    ]
  })),
  getCurrentUser: jest.fn(async () => ({
    uid: "u1",
    is_admin: false,
    restaurantId: "abc",
    name: "Adrian",
    email: "a@example.com"
  })),
  getRestaurants: jest.fn(async () => ([{ id: "abc", name: "Adrian's Cafe" }])),
  addMenuItem: jest.fn(async (rid, data) => ({ id: Math.random().toString(36).slice(2), ...data })),
};
