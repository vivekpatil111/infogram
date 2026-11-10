import React from 'react';

const Navbar = () => {
  return (
    <div className="fixed bottom-0 w-full max-w-md left-1/2 -translate-x-1/2 bg-black border-t border-zinc-800 h-16 flex justify-around items-center px-4 z-50">
      <button className="text-2xl">🏠</button>
      <button className="text-2xl">🔍</button>
      <button className="text-2xl bg-white text-black rounded-lg px-2 py-1">+</button>
      <button className="text-2xl">🎬</button>
      <div className="w-6 h-6 rounded-full bg-gray-500 border border-white" />
    </div>
  );
};

export default Navbar;
