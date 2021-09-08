import axios from "axios";

const Axios = () => {
  return axios.create({
    baseURL: process.env.REACT_APP_DEV_SERVER_API
      ? process.env.REACT_APP_DEV_SERVER_API
      : "/",
    method: "post",
    headers: { "Content-type": "application/json" },
    timeout: 5000,
    withCredentials: false,
  });
};

export default Axios;
