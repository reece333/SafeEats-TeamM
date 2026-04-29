/**
 * @jest-environment jsdom
 */
import React from "react";
import { render, screen, waitFor } from "@testing-library/react";
import ProfilePage from "../components/General/ProfilePage.jsx";
import { api } from "../services/api.js";

const mockNavigate = jest.fn();

jest.mock(
  "react-router-dom",
  () => ({
    useNavigate: () => mockNavigate,
  }),
  { virtual: true }
);

jest.mock("../services/api.js");

describe("ProfilePage auth and role coverage", () => {
  beforeEach(() => {
    jest.clearAllMocks();
    localStorage.clear();
  });

  test("redirects to landing page when unauthenticated", async () => {
    render(<ProfilePage />);

    await waitFor(() => {
      expect(mockNavigate).toHaveBeenCalledWith("/");
    });
    expect(api.getCurrentUser).not.toHaveBeenCalled();
  });

  test("renders admin role and restaurant id from profile payload", async () => {
    localStorage.setItem("auth_token", "token");
    api.getCurrentUser.mockResolvedValue({
      email: "admin@example.com",
      name: "Admin User",
      is_admin: true,
      restaurantId: "rest-123",
    });

    render(<ProfilePage />);

    expect(await screen.findByText("My Profile")).toBeInTheDocument();
    expect(screen.getByText("admin@example.com")).toBeInTheDocument();
    expect(screen.getByText("Admin User")).toBeInTheDocument();
    expect(screen.getByText("Administrator")).toBeInTheDocument();
    expect(screen.getByText("rest-123")).toBeInTheDocument();
  });

  test("clears auth and redirects on unauthorized API error", async () => {
    localStorage.setItem("auth_token", "token");
    api.getCurrentUser.mockRejectedValue({
      response: { status: 401 },
    });

    render(<ProfilePage />);

    await waitFor(() => {
      expect(mockNavigate).toHaveBeenCalledWith("/");
    });
    expect(localStorage.getItem("auth_token")).toBeNull();
  });
});
