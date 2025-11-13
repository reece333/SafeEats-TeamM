/**
 * @jest-environment jsdom
 */
import React from "react";
import { render, screen, fireEvent, waitFor, within } from "@testing-library/react";
import { api } from "../services/api.js";
import ManageMenuItems from "../components/Menu/ManageMenuItems.jsx";

// --- Router mocks ---
const mockUseParams = jest.fn(() => ({ restaurantId: "abc" }));
const mockNavigate = jest.fn();

// Treat react-router-dom as a virtual mock so Jest never needs the real package
jest.mock(
  "react-router-dom",
  () => ({
    useParams: () => mockUseParams(),
    useNavigate: () => mockNavigate,
  }),
  { virtual: true }
);

// Mock api module
jest.mock("../services/api.js");

// jsdom doesn't implement scrollIntoView; avoid crashing effects
beforeAll(() => {
  if (!HTMLElement.prototype.scrollIntoView) {
    // eslint-disable-next-line no-extend-native
    HTMLElement.prototype.scrollIntoView = jest.fn();
  }
});

const renderComponent = () => render(<ManageMenuItems />);

beforeEach(() => {
  jest.clearAllMocks();
  localStorage.clear();

  // Default user has access to restaurantId 'abc'
  api.getCurrentUser.mockResolvedValue({
    uid: "u1",
    is_admin: false,
    restaurantId: "abc",
    name: "Adrian",
    email: "a@example.com",
  });

  api.getRestaurants.mockResolvedValue([{ id: "abc", name: "Adrian's Cafe" }]);
  api.ingestMenuImage.mockResolvedValue({ items: [] });
  api.addMenuItem.mockImplementation(async (rid, data) => ({ id: "m1", ...data }));

  mockUseParams.mockReturnValue({ restaurantId: "abc" });
});

describe("ManageMenuItems", () => {
  test("auth gate: navigates to / when no user", async () => {
    api.getCurrentUser.mockResolvedValueOnce(null);
    renderComponent();

    await waitFor(() => {
      expect(mockNavigate).toHaveBeenCalledTimes(1);
      expect(mockNavigate).toHaveBeenCalledWith(
        "/",
        expect.objectContaining({
          state: expect.objectContaining({
            returnTo: "/restaurant/abc/menu",
          }),
        })
      );
    });
  });

  test("adds a new empty form (smoke)", async () => {
    renderComponent();

    // wait for initial load
    await screen.findByText(/Add Menu Items/i);

    const addBtn = screen.getByTitle(/Add another item/i);
    fireEvent.click(addBtn);

    expect(screen.getByText(/Menu Item #1/)).toBeInTheDocument();
    expect(screen.getByText(/Menu Item #2/)).toBeInTheDocument();
  });

  test("delete uses confirmation dialog (cancel keeps form, confirm removes)", async () => {
    renderComponent();
    await screen.findByText(/Add Menu Items/i);

    const formHeader = screen.getByText(/Menu Item #1/i);
    const form = formHeader.closest("div");
    const removeBtn = within(form).getByRole("button", { name: /Remove/i });

    fireEvent.click(removeBtn);

    // dialog appears
    const dialog = await screen.findByText(/Confirm Deletion/i);
    const dialogBox = dialog.closest("div").parentElement; // container with buttons

    // cancel keeps the form – pick the Cancel inside the dialog
    const dialogCancel = within(dialogBox).getByRole("button", { name: "Cancel" });
    fireEvent.click(dialogCancel);
    expect(screen.getByText(/Menu Item #1/)).toBeInTheDocument();

    // try again and confirm
    fireEvent.click(removeBtn);
    const dialog2 = await screen.findByText(/Confirm Deletion/i);
    const dialogBox2 = dialog2.closest("div").parentElement;
    const confirmBtn = within(dialogBox2).getByRole("button", { name: /Yes, Delete/i });
    fireEvent.click(confirmBtn);

    await waitFor(() => {
      expect(screen.queryByText(/Menu Item #1/)).not.toBeInTheDocument();
    });
  });

  test("ingest seeds multiple forms from /ai/ingest-menu result", async () => {
    api.ingestMenuImage.mockResolvedValueOnce({
      items: [
        {
          name: "Salad",
          description: "Green",
          price: 899,
          allergens: [],
          dietaryCategories: [],
          ingredients: "lettuce",
        },
        {
          name: "Soup",
          description: "Tomato",
          price: 499,
          allergens: ["milk"],
          dietaryCategories: [],
          ingredients: "tomato",
        },
      ],
    });

    renderComponent();
    await screen.findByText(/Add Menu Items/i);

    // Trigger file input
    const fileInput = document.getElementById("file-upload");
    const file = new File(["fake"], "menu.png", { type: "image/png" });
    fireEvent.change(fileInput, { target: { files: [file] } });

    await screen.findByText(/Imported 2 items/i);
    expect(screen.getByText(/Menu Item #2/)).toBeInTheDocument();
    expect(screen.getByText(/Menu Item #3/)).toBeInTheDocument();
  });

  test("Add All Items filters invalid rows, posts in parallel, sets localStorage and navigates back", async () => {
    renderComponent();
    await screen.findByText(/Add Menu Items/i);

    // Fill first form minimally – use placeholders instead of labels
    const nameInput = screen.getByPlaceholderText(/Item Name/i);
    fireEvent.change(nameInput, { target: { value: "Pizza" } });

    const descInput = screen.getByPlaceholderText(/Description/i);
    fireEvent.change(descInput, { target: { value: "Cheesy" } });

    const priceInput = screen.getByPlaceholderText(/Price/i);
    fireEvent.change(priceInput, {
      target: { value: "1299", selectionStart: 4 },
    });

    // Add second (invalid) form
    const addBtn = screen.getByTitle(/Add another item/i);
    fireEvent.click(addBtn);

    const addAll = screen.getByRole("button", { name: /Add All Items/i });
    fireEvent.click(addAll);

    await waitFor(() => {
      expect(api.addMenuItem).toHaveBeenCalledTimes(1);
    });

    expect(localStorage.getItem("menuItemsAdded")).toBe("true");
    expect(localStorage.getItem("menuItemsAddedCount")).toBe("1");

    // Should navigate back to restaurant page
    expect(mockNavigate).toHaveBeenCalledWith("/restaurant/abc");
  });
});
