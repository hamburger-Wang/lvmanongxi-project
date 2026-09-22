"use client";

import { useEffect, useRef } from "react";
import * as THREE from "three";
import type { AnalysisResult, CropCell } from "@/lib/api";

type FieldSceneProps = {
  result: AnalysisResult | null;
  selectedCell?: CropCell | null;
  colorMode?: "growth" | "crop";
  onSelectCell?: (cell: CropCell | null) => void;
};

const cropShapes: Record<string, { width: number; heightBoost: number; density: number }> = {
  corn: { width: 0.36, heightBoost: 1.25, density: 1 },
  wheat: { width: 0.42, heightBoost: 0.66, density: 0.8 },
  rice: { width: 0.48, heightBoost: 0.5, density: 1.2 },
  potato: { width: 0.56, heightBoost: 0.38, density: 0.7 },
  class_one: { width: 0.38, heightBoost: 1.08, density: 1 },
  class_two: { width: 0.46, heightBoost: 0.84, density: 1 },
  other: { width: 0.5, heightBoost: 0.28, density: 0.4 },
};

export default function FieldScene({ result, selectedCell, colorMode = "growth", onSelectCell }: FieldSceneProps) {
  const mountRef = useRef<HTMLDivElement | null>(null);
  const cellsRef = useRef<CropCell[]>([]);
  const selectedRef = useRef<CropCell | null>(selectedCell ?? null);

  useEffect(() => {
    selectedRef.current = selectedCell ?? null;
  }, [selectedCell]);

  useEffect(() => {
    const mount = mountRef.current;
    if (!mount || !result) return;

    cellsRef.current = result.scene.cells;

    const scene = new THREE.Scene();
    scene.background = new THREE.Color("#eef3ed");

    const camera = new THREE.PerspectiveCamera(42, mount.clientWidth / mount.clientHeight, 0.1, 200);
    camera.position.set(18, 19, 24);
    camera.lookAt(0, 0, 0);

    const renderer = new THREE.WebGLRenderer({ antialias: true, alpha: true });
    renderer.setPixelRatio(Math.min(window.devicePixelRatio, 2));
    renderer.setSize(mount.clientWidth, mount.clientHeight);
    renderer.shadowMap.enabled = true;
    mount.appendChild(renderer.domElement);

    const ambient = new THREE.HemisphereLight("#ffffff", "#9cac92", 2.5);
    scene.add(ambient);

    const sun = new THREE.DirectionalLight("#fff2ce", 3.4);
    sun.position.set(12, 20, 14);
    sun.castShadow = true;
    scene.add(sun);

    const gridSize = result.source.gridSize;
    const offset = (gridSize - 1) / 2;

    const base = new THREE.Mesh(
      new THREE.BoxGeometry(gridSize + 1.8, 0.34, gridSize + 1.8),
      new THREE.MeshStandardMaterial({ color: "#d6caa5", roughness: 0.88 })
    );
    base.position.y = -0.28;
    base.receiveShadow = true;
    scene.add(base);

    const cellGroup = new THREE.Group();
    scene.add(cellGroup);

    const clickTargets: THREE.Object3D[] = [];
    const color = new THREE.Color();

    result.scene.cells.forEach((cell, index) => {
      const shape = cropShapes[cell.crop] ?? cropShapes.other;
      const height = Math.max(0.08, cell.height * shape.heightBoost);
      const material = new THREE.MeshStandardMaterial({
        color: colorFromCell(cell, colorMode, result.scene.cropProfiles),
        roughness: 0.68,
        metalness: 0.02,
      });
      const tile = new THREE.Mesh(new THREE.BoxGeometry(0.86, height, 0.86), material);
      tile.position.set(cell.x - offset, height / 2, cell.z - offset);
      tile.castShadow = true;
      tile.receiveShadow = true;
      tile.userData = { index };
      cellGroup.add(tile);
      clickTargets.push(tile);

      if ((cell.x + cell.z) % Math.max(1, Math.round(3 / shape.density)) === 0 && cell.growth > 0.28) {
        const plant = makePlant(cell, shape, colorMode, result.scene.cropProfiles);
        plant.position.set(cell.x - offset, height + 0.04, cell.z - offset);
        cellGroup.add(plant);
      }
    });

    const outline = new THREE.LineSegments(
      new THREE.EdgesGeometry(new THREE.BoxGeometry(gridSize + 1.9, 0.36, gridSize + 1.9)),
      new THREE.LineBasicMaterial({ color: "#8a9b70", transparent: true, opacity: 0.45 })
    );
    outline.position.y = -0.25;
    scene.add(outline);

    const marker = new THREE.Mesh(
      new THREE.RingGeometry(0.56, 0.72, 32),
      new THREE.MeshBasicMaterial({ color: "#1f7a3b", side: THREE.DoubleSide, transparent: true, opacity: 0.75 })
    );
    marker.rotation.x = -Math.PI / 2;
    marker.visible = false;
    scene.add(marker);

    const raycaster = new THREE.Raycaster();
    const pointer = new THREE.Vector2();
    let dragging = false;
    let lastX = 0;
    let lastY = 0;
    let rotationY = -0.7;
    let rotationX = 0.64;
    let distance = 32;

    function updateCamera() {
      camera.position.x = Math.sin(rotationY) * Math.cos(rotationX) * distance;
      camera.position.y = Math.sin(rotationX) * distance;
      camera.position.z = Math.cos(rotationY) * Math.cos(rotationX) * distance;
      camera.lookAt(0, 0, 0);
    }
    updateCamera();

    function updateMarker() {
      const selected = selectedRef.current;
      if (!selected) {
        marker.visible = false;
        return;
      }
      marker.visible = true;
      marker.position.set(selected.x - offset, selected.height * 1.6 + 0.16, selected.z - offset);
    }

    function selectFromPointer(event: PointerEvent) {
      const rect = renderer.domElement.getBoundingClientRect();
      pointer.x = ((event.clientX - rect.left) / rect.width) * 2 - 1;
      pointer.y = -((event.clientY - rect.top) / rect.height) * 2 + 1;
      raycaster.setFromCamera(pointer, camera);
      const hit = raycaster.intersectObjects(clickTargets, false)[0];
      const cell = hit ? cellsRef.current[hit.object.userData.index] : null;
      selectedRef.current = cell;
      onSelectCell?.(cell);
      updateMarker();
    }

    renderer.domElement.addEventListener("pointerdown", (event) => {
      dragging = true;
      lastX = event.clientX;
      lastY = event.clientY;
    });
    renderer.domElement.addEventListener("pointermove", (event) => {
      if (!dragging) return;
      const dx = event.clientX - lastX;
      const dy = event.clientY - lastY;
      lastX = event.clientX;
      lastY = event.clientY;
      rotationY -= dx * 0.008;
      rotationX = THREE.MathUtils.clamp(rotationX + dy * 0.006, 0.22, 1.12);
      updateCamera();
    });
    renderer.domElement.addEventListener("pointerup", (event) => {
      dragging = false;
      selectFromPointer(event);
    });
    renderer.domElement.addEventListener("wheel", (event) => {
      distance = THREE.MathUtils.clamp(distance + event.deltaY * 0.018, 20, 52);
      updateCamera();
    });

    const resizeObserver = new ResizeObserver(() => {
      camera.aspect = mount.clientWidth / mount.clientHeight;
      camera.updateProjectionMatrix();
      renderer.setSize(mount.clientWidth, mount.clientHeight);
    });
    resizeObserver.observe(mount);

    let frame = 0;
    let animationId = 0;
    function animate() {
      frame += 0.01;
      cellGroup.position.y = Math.sin(frame) * 0.015;
      updateMarker();
      renderer.render(scene, camera);
      animationId = requestAnimationFrame(animate);
    }
    animate();

    return () => {
      cancelAnimationFrame(animationId);
      resizeObserver.disconnect();
      mount.removeChild(renderer.domElement);
      renderer.dispose();
      scene.traverse((object) => {
        if (object instanceof THREE.Mesh) {
          object.geometry.dispose();
          if (Array.isArray(object.material)) {
            object.material.forEach((item) => item.dispose());
          } else {
            object.material.dispose();
          }
        }
      });
    };
  }, [result, colorMode, onSelectCell]);

  return <div ref={mountRef} className="scene-canvas" aria-label="三维农田长势场景" />;
}

function makePlant(
  cell: CropCell,
  shape: { width: number; heightBoost: number },
  colorMode: "growth" | "crop",
  cropProfiles: AnalysisResult["scene"]["cropProfiles"]
) {
  const group = new THREE.Group();
  const growthColor = new THREE.Color(colorFromCell(cell, colorMode, cropProfiles));
  const stemHeight = Math.max(0.18, cell.growth * shape.heightBoost * 0.9);
  const stem = new THREE.Mesh(
    new THREE.CylinderGeometry(shape.width * 0.08, shape.width * 0.12, stemHeight, 6),
    new THREE.MeshStandardMaterial({ color: growthColor, roughness: 0.8 })
  );
  stem.position.y = stemHeight / 2;
  stem.castShadow = true;
  group.add(stem);

  const canopy = new THREE.Mesh(
    new THREE.ConeGeometry(shape.width * (0.34 + cell.growth * 0.25), stemHeight * 0.55, 6),
    new THREE.MeshStandardMaterial({ color: growthColor.offsetHSL(0, 0.06, 0.05), roughness: 0.75 })
  );
  canopy.position.y = stemHeight + stemHeight * 0.2;
  canopy.castShadow = true;
  group.add(canopy);
  return group;
}

function colorFromCell(
  cell: CropCell,
  colorMode: "growth" | "crop",
  cropProfiles: AnalysisResult["scene"]["cropProfiles"]
) {
  if (colorMode === "crop") {
    return cropProfiles[cell.crop]?.baseColor ?? "#727d72";
  }
  if (cell.anomaly > 0.55) return "#bb553f";
  if (cell.growth < 0.45) return "#c49a3a";
  if (cell.growth < 0.68) return "#8aa64a";
  if (cell.crop === "class_one") return "#2f7e43";
  if (cell.crop === "class_two") return "#2f9866";
  if (cell.crop === "rice") return "#2f9866";
  if (cell.crop === "wheat") return "#74a048";
  return "#2f7e43";
}
