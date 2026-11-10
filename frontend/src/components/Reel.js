import React, { useState } from 'react';

const Reel = ({ videoUrl, username, caption, resources }) => {
  const [showDrawer, setShowDrawer] = useState(false);

  return (
    <div className="reel-item bg-black w-full max-w-md mx-auto">
      {/* Video Element */}
      <video 
        src={videoUrl} 
        className="h-full w-full object-cover" 
        loop 
        muted 
        autoPlay 
        playsInline
      />

      {/* UI Overlay */}
      <div className="absolute inset-0 flex flex-col justify-end p-4 bg-gradient-to-t from-black/60 to-transparent">
        
        {/* User & Caption */}
        <div className="mb-12">
          <div className="flex items-center gap-2 mb-2">
            <div className="w-8 h-8 rounded-full bg-gray-400 border border-white" />
            <span className="font-semibold text-sm">{username}</span>
            <button className="text-xs border border-white px-2 py-0.5 rounded-md">Follow</button>
          </div>
          <p className="text-sm line-clamp-2">{caption}</p>
        </div>

        {/* Action Buttons (Right Side) */}
        <div className="absolute right-4 bottom-24 flex flex-col items-center gap-6">
          <div className="flex flex-col items-center">
            <button className="text-2xl">❤️</button>
            <span className="text-xs">12k</span>
          </div>
          <div className="flex flex-col items-center">
            <button className="text-2xl">💬</button>
            <span className="text-xs">450</span>
          </div>
          <div className="flex flex-col items-center">
            <button className="text-2xl">✈️</button>
            <span className="text-xs">Share</span>
          </div>
          {/* THE INFOGRAM BUTTON: Resource Drawer */}
          <div className="flex flex-col items-center">
            <button 
              onClick={() => setShowDrawer(true)} 
              className="text-2xl bg-blue-600 p-2 rounded-full animate-bounce"
            >
              📚
            </button>
            <span className="text-xs font-bold text-blue-400">Info</span>
          </div>
        </div>
      </div>

      {/* Resource Drawer (The Infogram Pivot) */}
      {showDrawer && (
        <div className="absolute inset-0 bg-black/80 z-50 flex items-end animate-slide-up">
          <div className="bg-zinc-900 w-full rounded-t-3xl p-6 max-h-[80vh] overflow-y-auto">
            <div className="flex justify-between items-center mb-4">
              <h3 className="text-lg font-bold">Knowledge Resources</h3>
              <button onClick={() => setShowDrawer(false)} className="text-2xl">✕</button>
            </div>
            <div className="space-y-4">
              {resources.map((res, idx) => (
                <div key={idx} className="p-3 bg-zinc-800 rounded-lg flex justify-between items-center">
                  <span>{res.label}</span>
                  <a href={res.url} className="text-blue-400 text-sm underline">View Link</a>
                </div>
              ))}
            </div>
          </div>
        </div>
      )}
    </div>
  );
};

export default Reel;
