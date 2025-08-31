import React from 'react';

const RegimeTest: React.FC = () => {
  return (
    <div style={{ 
      padding: '20px', 
      backgroundColor: 'white', 
      color: 'black',
      minHeight: '100vh'
    }}>
      <h1 style={{ color: 'red' }}>REGIME TEST PAGE</h1>
      <p style={{ color: 'blue', fontSize: '18px' }}>
        This is a simple test page to check if the routing is working.
      </p>
      <p style={{ color: 'green' }}>
        If you can see this text, the routing works and the issue is with the complex component.
      </p>
    </div>
  );
};

export default RegimeTest;