import React from 'react';

// Placeholders shaped like the content they stand in for, so pages don't jump when data lands.
export function PostSkeleton() {
  return <div className="post-skeleton" aria-hidden="true">
    <div className="sk-row"><i className="sk sk-avatar"/><span><i className="sk sk-line w40"/><i className="sk sk-line w25"/></span></div>
    <i className="sk sk-media"/>
    <i className="sk sk-line w30"/><i className="sk sk-line w80"/>
  </div>;
}

export function ListSkeleton({ rows = 5 }) {
  return <div className="list-skeleton" aria-label="Loading" role="status">
    {Array.from({ length: rows }, (_, i) => <div className="sk-row" key={i}>
      <i className="sk sk-avatar"/><span><i className="sk sk-line" style={{ width: `${55 - (i % 3) * 10}%` }}/><i className="sk sk-line w25"/></span>
    </div>)}
  </div>;
}

export function Spinner({ label = 'Loading' }) {
  return <span className="spinner" role="status" aria-label={label}/>;
}
