import { createContext, useContext } from 'react';

// App-wide actions and state, so pages and cards don't prop-drill:
// { currentUser, setCurrentUser, showToast, openProfile, openPost, openShare,
//   openReport, openSheet, openChat, openCreate, followUser, followStatusOf,
//   refreshUnread, navigate }
export const AppContext = createContext(null);
export const useApp = () => useContext(AppContext);
