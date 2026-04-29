/**
 * @jest-environment jsdom
 */
import React from "react";
import { render, screen, waitFor, fireEvent } from "@testing-library/react";
import DashboardPage from "../components/General/DashboardPage.jsx";
import { api } from "../services/api.js";

const mockNavigate = jest.fn();

jest.mock(
  "react-router-dom",
  () => ({
    useNavigate: () => mockNavigate,
    Link: ({ children, ...props }) => <a {...props}>{children}</a>,
  }),
  { virtual: true }
);

jest.mock("../services/api.js");

describe("DashboardPage auth/role coverage", () => {
  beforeEach(() => {
    jest.clearAllMocks();
    localStorage.clear();
  });

  test("redirects to landing when token is missing", async () => {
    render(<DashboardPage />);

    await waitFor(() => {
      expect(mockNavigate).toHaveBeenCalledWith("/", { replace: true });
    });
    expect(api.getCurrentUser).not.toHaveBeenCalled();
  });

  test("redirects admins to restaurant list", async () => {
    localStorage.setItem("auth_token", "token");
    api.getCurrentUser.mockResolvedValue({
      uid: "admin1",
      is_admin: true,
      email: "admin@example.com",
      restaurants: [],
    });

    render(<DashboardPage />);

    await waitFor(() => {
      expect(mockNavigate).toHaveBeenCalledWith("/restaurant-list", { replace: true });
    });
  });

  test("renders restaurant memberships and sets context on open", async () => {
    localStorage.setItem("auth_token", "token");
    api.getCurrentUser.mockResolvedValue({
      uid: "u1",
      is_admin: false,
      email: "u1@example.com",
      restaurants: [
        { id: "r-owner", name: "Owned Place", role: "manager", is_owner: true },
        { id: "r-staff", name: "Staff Place", role: "staff", is_owner: false },
      ],
    });
    api.setCurrentRestaurant.mockImplementation(() => {});

    render(<DashboardPage />);

    expect(await screen.findByText("My restaurants")).toBeInTheDocument();
    expect(screen.getByText("Owned Place")).toBeInTheDocument();
    expect(screen.getByText("Staff Place")).toBeInTheDocument();
    expect(screen.getByText("Owner")).toBeInTheDocument();
    expect(screen.getByText("Team · Staff")).toBeInTheDocument();

    fireEvent.click(screen.getAllByText("Open")[0]);
    expect(api.setCurrentRestaurant).toHaveBeenCalledWith("r-owner", "manager");
  });
});
