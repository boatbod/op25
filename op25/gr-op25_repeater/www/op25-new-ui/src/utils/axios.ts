import axios from "axios";

export const AXIOS_BASE_URL = process.env.REACT_APP_DEV_SERVER_API
  ? process.env.REACT_APP_DEV_SERVER_API
  : "/";

const Axios = () => {
  return axios.create({
    baseURL: AXIOS_BASE_URL,
    method: "post",
    headers: { "Content-type": "application/json" },
    timeout: 5000,
    withCredentials: false,
  });
};

export default Axios;
