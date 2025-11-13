
/**
 * @jest-environment jsdom
 */
import React from "react";
import { render, screen, fireEvent, waitFor } from "@testing-library/react";
import MenuItemForm from "../components/Menu/MenuItemForm.jsx";

import { api } from "../services/api.js";

// auto-mock the api module
jest.mock("../services/api.js", () => ({
  api: {
    parseIngredientsWithAI: jest.fn(async (text) => {
      if (text === "ERR") {
        const err = new Error("Failed to parse ingredients");
        err.message = "Failed to parse ingredients";
        throw err;
      }
      return {
        allergens: ["milk", "wheat"],
        dietaryCategories: ["vegetarian"],
        extractedIngredients: ["milk", "wheat", "salt"]
      };
    })
  }
}));

const setup = (props = {}) => {
  return render(<MenuItemForm formIndex={0} onRemove={jest.fn()} onFormChange={jest.fn()} restaurantOptions={[]} {...props} />);
};

describe("MenuItemForm", () => {
  test("Parse button disabled when ingredients empty; enabled when not", () => {
    setup();
    const parseBtn = screen.getByRole("button", { name: /parse/i });
    expect(parseBtn).toBeDisabled();
    const ingredients = screen.getByLabelText(/ingredients/i);
    fireEvent.change(ingredients, { target: { value: "milk, wheat" } });
    expect(parseBtn).toBeEnabled();
  });

  test("Successful parse updates allergens and ingredients", async () => {
    setup();
    fireEvent.change(screen.getByLabelText(/ingredients/i), { target: { value: "milk, wheat" } });
    fireEvent.click(screen.getByRole("button", { name: /parse/i }));
    await waitFor(() => {
      // Parsed allergens text appears
      expect(screen.getByText(/Parsed allergens:/i)).toBeInTheDocument();
      expect(screen.getByText(/Milk/)).toBeInTheDocument();
      expect(screen.getByText(/Wheat/)).toBeInTheDocument();
    });
    expect(api.parseIngredientsWithAI).toHaveBeenCalledWith("milk, wheat");
  });

  test("Failed parse shows error message", async () => {
    setup();
    fireEvent.change(screen.getByLabelText(/ingredients/i), { target: { value: "ERR" } });
    fireEvent.click(screen.getByRole("button", { name: /parse/i }));
    await waitFor(() => {
      expect(screen.getByText(/Failed to parse ingredients/i)).toBeInTheDocument();
    });
  });

  test("Price masking converts digits to $D.CC and maintains numeric price", () => {
    const onFormChange = jest.fn();
    setup({ onFormChange });

    const price = screen.getByLabelText(/price\*/i);
    // type "1" -> $0.01
    fireEvent.change(price, { target: { value: "1", selectionStart: 1 } });
    // type "12" -> $0.12
    fireEvent.change(price, { target: { value: "12", selectionStart: 2 } });
    // type "1299" -> $12.99
    fireEvent.change(price, { target: { value: "1299", selectionStart: 4 } });

    // We can't reliably test caret in jsdom, but we can assert the displayed value and that onFormChange eventually receives numeric price.
    expect(price.value).toBe("$12.99");

    // Change name to trigger onFormChange (component only emits after changes)
    fireEvent.change(screen.getByLabelText(/item name\*/i), { target: { value: "Pasta" } });

    // The component sends data upstream with price numeric
    // Wait for onFormChange to be called with price as number (priceNumeric becomes 12.99; price sent upstream equals numeric)
    expect(onFormChange).toHaveBeenCalled();
    const last = onFormChange.mock.calls.pop()[0];
    expect(typeof last.price).toBe("number");
    expect(last.price).toBeCloseTo(12.99, 2);
  });

  test("Allergen and dietary checkboxes toggle arrays", () => {
    const onFormChange = jest.fn();
    setup({ onFormChange });

    // Toggle Vegan and Milk
    const vegan = screen.getByLabelText(/Vegan/);
    const milk = screen.getByLabelText(/Milk/);

    fireEvent.click(vegan);
    fireEvent.click(milk);
    // Change description to force onFormChange update
    fireEvent.change(screen.getByLabelText(/Description\*/i), { target: { value: "desc" } });

    expect(onFormChange).toHaveBeenCalled();
    const data = onFormChange.mock.calls.pop()[0];
    expect(data.dietaryCategories).toContain("vegan");
    expect(data.allergens).toContain("milk");
  });
});
