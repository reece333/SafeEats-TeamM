/**
 * @jest-environment jsdom
 */
import React from "react";
import { render, screen, waitFor } from "@testing-library/react";
import RestaurantPage from "../components/Restaurant/RestaurantPage.jsx";
import { api } from "../services/api.js";

const mockNavigate = jest.fn();

jest.mock(
  "react-router-dom",
  () => ({
    useParams: () => ({ restaurantId: "abc" }),
    useNavigate: () => mockNavigate,
    Link: ({ children, ...props }) => <a {...props}>{children}</a>,
  }),
  { virtual: true }
);

jest.mock("../services/api.js");

describe("RestaurantPage archived menu visibility", () => {
  beforeEach(() => {
    jest.clearAllMocks();
    localStorage.clear();
    localStorage.setItem("auth_token", "token");

    api.getCurrentUser.mockResolvedValue({
      uid: "u1",
      is_admin: false,
      restaurants: [{ id: "abc", role: "manager" }],
    });
    api.getRestaurants.mockResolvedValue([
      { id: "abc", name: "Adrian's Cafe", cuisine_type: "Cafe" },
    ]);
    api.getMenuItems.mockResolvedValue([
      {
        id: "active-1",
        name: "Burger",
        description: "Fresh",
        price: 12.5,
        archived: false,
      },
      {
        id: "archived-1",
        name: "Secret Special",
        description: "No longer served",
        price: 15,
        archived: true,
      },
    ]);
    api.getRestaurantMembers.mockResolvedValue([]);
    api.setCurrentRestaurant.mockImplementation(() => {});
  });

  test("hides archived menu items on the restaurant page", async () => {
    render(<RestaurantPage />);

    expect(await screen.findByText("Burger")).toBeInTheDocument();
    await waitFor(() => {
      expect(screen.queryByText("Secret Special")).not.toBeInTheDocument();
    });
  });
});