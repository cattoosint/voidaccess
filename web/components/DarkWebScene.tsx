"use client";

import { useEffect, useRef } from "react";
import * as THREE from "three";

export default function DarkWebScene() {
  const mountRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (!mountRef.current) return;

    // SCENE SETUP
    const scene = new THREE.Scene();
    scene.fog = new THREE.FogExp2(0x080b0f, 0.05);

    // CAMERA
    const camera = new THREE.PerspectiveCamera(
      75,
      mountRef.current.clientWidth / mountRef.current.clientHeight,
      0.1,
      1000
    );
    camera.position.z = 5;

    // RENDERER
    const renderer = new THREE.WebGLRenderer({ alpha: true, antialias: true });
    renderer.setSize(mountRef.current.clientWidth, mountRef.current.clientHeight);
    renderer.setPixelRatio(Math.min(window.devicePixelRatio, 2));
    mountRef.current.appendChild(renderer.domElement);

    // PARTICLES / DATA STREAM
    const particleCount = 6000;
    const geometry = new THREE.BufferGeometry();
    const positions = new Float32Array(particleCount * 3);
    const colors = new Float32Array(particleCount * 3);
    const color = new THREE.Color();

    for (let i = 0; i < particleCount; i++) {
        // Tunnel effect
        const radius = 2 + Math.random() * 6;
        const theta = Math.random() * Math.PI * 2;
        const z = (Math.random() - 0.5) * 60; // Long tunnel

        positions[i * 3] = Math.cos(theta) * radius;     // x
        positions[i * 3 + 1] = Math.sin(theta) * radius; // y
        positions[i * 3 + 2] = z;                        // z

        // Themed colors
        const isAccent = Math.random() > 0.8;
        if (isAccent) {
            color.setHex(0x58a6ff); // void access blue accent
        } else {
            color.setHex(0x1c2128); // muted background color
        }

        colors[i * 3] = color.r;
        colors[i * 3 + 1] = color.g;
        colors[i * 3 + 2] = color.b;
    }

    geometry.setAttribute('position', new THREE.BufferAttribute(positions, 3));
    geometry.setAttribute('color', new THREE.BufferAttribute(colors, 3));

    const material = new THREE.PointsMaterial({
        size: 0.05,
        vertexColors: true,
        transparent: true,
        opacity: 0.8,
        blending: THREE.AdditiveBlending,
        fog: true
    });

    const particles = new THREE.Points(geometry, material);
    scene.add(particles);

    // ABSTRACT GRID TUNNEL
    const gridHelper = new THREE.GridHelper(40, 40, 0x58a6ff, 0x161b22);
    gridHelper.position.y = -3;
    scene.add(gridHelper);
    
    const gridHelperTop = new THREE.GridHelper(40, 40, 0x58a6ff, 0x161b22);
    gridHelperTop.position.y = 3;
    gridHelperTop.rotation.x = Math.PI;
    scene.add(gridHelperTop);

    // ANIMATION LOOP
    let animationFrameId: number;
    let clock = new THREE.Clock();

    const animate = function () {
      animationFrameId = requestAnimationFrame(animate);
      
      const delta = clock.getDelta();

      // Dive forward
      particles.position.z += delta * 5;
      particles.rotation.z -= delta * 0.05;

      if (particles.position.z > 30) {
          particles.position.z -= 60;
      }

      gridHelper.position.z += delta * 3;
      if(gridHelper.position.z > 10) {
        gridHelper.position.z -= 10;
      }
      
      gridHelperTop.position.z += delta * 3;
      if(gridHelperTop.position.z > 10) {
        gridHelperTop.position.z -= 10;
      }

      renderer.render(scene, camera);
    };

    animate();

    // RESIZE HANDLER
    const handleResize = () => {
        if (!mountRef.current) return;
        camera.aspect = mountRef.current.clientWidth / mountRef.current.clientHeight;
        camera.updateProjectionMatrix();
        renderer.setSize(mountRef.current.clientWidth, mountRef.current.clientHeight);
    };
    window.addEventListener('resize', handleResize);

    // CLEANUP
    return () => {
      window.removeEventListener('resize', handleResize);
      cancelAnimationFrame(animationFrameId);
      geometry.dispose();
      material.dispose();
      renderer.dispose();
      if (mountRef.current) {
        mountRef.current.removeChild(renderer.domElement);
      }
    };
  }, []);

  return (
    <div className="w-full h-full absolute inset-0 bg-[#080b0f] z-0 overflow-hidden pointer-events-none select-none">
      <div ref={mountRef} className="w-full h-full" />
      {/* Blend the left edge with the main login form */}
      <div className="absolute inset-y-0 left-0 w-32 bg-gradient-to-r from-[var(--bg-void)] to-transparent z-10" />
      {/* Optional vignette */}
      <div className="absolute inset-0 bg-[radial-gradient(ellipse_at_center,_var(--tw-gradient-stops))] from-transparent via-[#080b0f]/50 to-[#080b0f] opacity-80 z-10 pointer-events-none" />
    </div>
  );
}
