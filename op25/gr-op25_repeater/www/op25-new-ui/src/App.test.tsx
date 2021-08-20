import { render } from "@testing-library/react";
import { Provider } from "react-redux";
import { store } from "./redux/app/store";
import App from "./App";

// test('renders learn react link', () => {
//   const { getByText } = render(
//     <Provider store={store}>
//       <App />
//     </Provider>
//   );

//   expect(getByText(/learn/i)).toBeInTheDocument();
// });

test("placeholder", () => {
  const { getByText } = render(<div>Placeholder</div>);

  expect(getByText(/Placeholder/i)).toBeInTheDocument();
});
