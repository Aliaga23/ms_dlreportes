"""
Servicio YOLO para detección de objetos
YOLOv8 para detección de checkboxes, formularios y elementos
"""

from ultralytics import YOLO
import cv2
import numpy as np
from PIL import Image
import time

class YOLOService:
    def __init__(self):
        """
        Inicializar YOLO para detección de elementos de formulario
        """
        try:
            # Modelos YOLO disponibles
            self.models = {
                'nano': None,
                'small': None,
                'medium': None,
                'large': None
            }
            
            # Intentar cargar modelo nano (más rápido)
            try:
                self.model = YOLO('yolov8n.pt')
                self.model_name = 'yolov8n'
                print(f"YOLO Nano cargado")
            except:
                try:
                    self.model = YOLO('yolov8s.pt')
                    self.model_name = 'yolov8s'
                    print(f"YOLO Small cargado")
                except:
                    print("No se pudo cargar ningún modelo YOLO")
                    self.model = None
                    self.model_name = None
            
            # Clases COCO estándar útiles para análisis de documentos
            self.form_classes = {
                0: 'person', 15: 'cat', 16: 'dog', 17: 'horse',
                39: 'bottle', 41: 'cup', 64: 'mouse', 66: 'keyboard',
                67: 'cell phone', 72: 'tv', 73: 'laptop', 74: 'mouse',
                76: 'keyboard', 77: 'cell phone'
            }
            
            # Configuraciones de detección específicas
            self.detection_config = {
                'min_area': 100,
                'max_area': 50000,
                'aspect_ratio_range': (0.2, 5.0),
                'confidence_threshold': 0.3,
                'nms_threshold': 0.5
            }
            
        except Exception as e:
            print(f"Error inicializando YOLO: {e}")
            self.model = None
            self.model_name = None
    
    def detect_objects(self, image, confidence_threshold=0.5):
        """
        Detectar objetos en la imagen usando YOLO con análisis avanzado
        """
        if self.model is None:
            return {
                "error": "YOLO no disponible",
                "detections": [],
                "total": 0,
                "statistics": {}
            }
        
        try:
            # Ejecutar detección con configuración optimizada
            results = self.model(
                image, 
                conf=confidence_threshold,
                iou=self.detection_config['nms_threshold'],
                verbose=False
            )
            
            detections = []
            areas = []
            confidences = []
            class_distribution = {}
            
            # Obtener dimensiones de imagen
            h, w = image.shape[:2]
            total_image_area = h * w
            
            for result in results:
                for box in result.boxes:
                    confidence = box.conf.item()
                    if confidence > confidence_threshold:
                        # Coordenadas y área
                        x1, y1, x2, y2 = box.xyxy[0].tolist()
                        width = x2 - x1
                        height = y2 - y1
                        area = width * height
                        
                        # Validar área mínima/máxima
                        if (area < self.detection_config['min_area'] or 
                            area > self.detection_config['max_area']):
                            continue
                        
                        # Validar aspect ratio
                        aspect_ratio = width / height if height > 0 else 0
                        min_ar, max_ar = self.detection_config['aspect_ratio_range']
                        if not (min_ar <= aspect_ratio <= max_ar):
                            continue
                        
                        class_id = int(box.cls.item())
                        class_name = self.model.names[class_id]
                        
                        # Calcular posición relativa
                        center_x = (x1 + x2) / 2
                        center_y = (y1 + y2) / 2
                        relative_x = center_x / w
                        relative_y = center_y / h
                        area_percentage = (area / total_image_area) * 100
                        
                        detection = {
                            'bbox': {
                                'x1': int(x1), 'y1': int(y1),
                                'x2': int(x2), 'y2': int(y2),
                                'width': int(width), 'height': int(height),
                                'center_x': int(center_x), 'center_y': int(center_y),
                                'area': int(area)
                            },
                            'class_id': class_id,
                            'class_name': class_name,
                            'confidence': float(confidence),
                            'metrics': {
                                'aspect_ratio': float(aspect_ratio),
                                'relative_position': {
                                    'x': float(relative_x),
                                    'y': float(relative_y)
                                },
                                'area_percentage': float(area_percentage),
                                'density_score': float(confidence * area_percentage / 100)
                            }
                        }
                        
                        detections.append(detection)
                        areas.append(area)
                        confidences.append(confidence)
                        
                        # Distribución de clases
                        if class_name not in class_distribution:
                            class_distribution[class_name] = 0
                        class_distribution[class_name] += 1
            
            # Calcular estadísticas avanzadas
            statistics = self._calculate_detection_statistics(
                detections, areas, confidences, class_distribution, total_image_area
            )
            
            return {
                "model": self.model_name,
                "detections": detections,
                "total": len(detections),
                "statistics": statistics,
                "error": None
            }
            
        except Exception as e:
            return {
                "error": f"Error en detección YOLO: {str(e)}",
                "detections": [],
                "total": 0,
                "statistics": {}
            }
    
    def _calculate_detection_statistics(self, detections, areas, confidences, class_distribution, total_area):
        """
        Calcular estadísticas avanzadas de las detecciones
        """
        if not detections:
            return {
                "total_objects": 0,
                "coverage_percentage": 0,
                "density_score": 0,
                "confidence_stats": {},
                "size_distribution": {},
                "spatial_distribution": {},
                "class_distribution": {}
            }
        
        # Estadísticas básicas
        total_detection_area = sum(areas)
        coverage_percentage = (total_detection_area / total_area) * 100
        
        # Estadísticas de confianza
        avg_confidence = np.mean(confidences)
        std_confidence = np.std(confidences)
        min_confidence = np.min(confidences)
        max_confidence = np.max(confidences)
        
        # Distribución de tamaños
        area_quartiles = np.percentile(areas, [25, 50, 75])
        size_categories = {
            'small': len([a for a in areas if a < area_quartiles[0]]),
            'medium': len([a for a in areas if area_quartiles[0] <= a < area_quartiles[2]]),
            'large': len([a for a in areas if a >= area_quartiles[2]])
        }
        
        # Distribución espacial (cuadrantes)
        quadrants = {'top_left': 0, 'top_right': 0, 'bottom_left': 0, 'bottom_right': 0}
        for detection in detections:
            rel_pos = detection['metrics']['relative_position']
            if rel_pos['x'] < 0.5 and rel_pos['y'] < 0.5:
                quadrants['top_left'] += 1
            elif rel_pos['x'] >= 0.5 and rel_pos['y'] < 0.5:
                quadrants['top_right'] += 1
            elif rel_pos['x'] < 0.5 and rel_pos['y'] >= 0.5:
                quadrants['bottom_left'] += 1
            else:
                quadrants['bottom_right'] += 1
        
        # Score de densidad ponderado
        density_scores = [d['metrics']['density_score'] for d in detections]
        weighted_density = np.average(density_scores, weights=confidences)
        
        return {
            "total_objects": len(detections),
            "coverage_percentage": float(coverage_percentage),
            "density_score": float(weighted_density),
            "confidence_stats": {
                "mean": float(avg_confidence),
                "std": float(std_confidence),
                "min": float(min_confidence),
                "max": float(max_confidence),
                "quartiles": [float(q) for q in np.percentile(confidences, [25, 50, 75])]
            },
            "size_distribution": {
                "area_quartiles": [float(q) for q in area_quartiles],
                "categories": size_categories,
                "total_area": float(total_detection_area),
                "avg_area": float(np.mean(areas))
            },
            "spatial_distribution": {
                "quadrants": quadrants,
                "center_of_mass": self._calculate_center_of_mass(detections)
            },
            "class_distribution": class_distribution
        }
    
    def _calculate_center_of_mass(self, detections):
        """
        Calcular centro de masa de las detecciones
        """
        if not detections:
            return {"x": 0.5, "y": 0.5}
        
        weighted_x = sum(d['metrics']['relative_position']['x'] * d['confidence'] for d in detections)
        weighted_y = sum(d['metrics']['relative_position']['y'] * d['confidence'] for d in detections)
        total_weight = sum(d['confidence'] for d in detections)
        
        return {
            "x": float(weighted_x / total_weight),
            "y": float(weighted_y / total_weight)
        }
    
    def detect_checkboxes(self, image):
        """
        Detectar checkboxes con análisis morfológico avanzado
        """
        results = self.detect_objects(image, confidence_threshold=0.3)
        
        # Análisis adicional con OpenCV para checkboxes
        gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
        edges = cv2.Canny(gray, 50, 150)
        contours, _ = cv2.findContours(edges, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        
        checkbox_candidates = []
        morphological_candidates = []
        
        # Análisis YOLO tradicional
        for detection in results.get("detections", []):
            bbox = detection['bbox']
            width, height = bbox['width'], bbox['height']
            area = width * height
            aspect_ratio = width / height if height > 0 else 0
            
            # Heurística mejorada para checkboxes
            if (10 < width < 80 and 10 < height < 80 and 
                0.6 < aspect_ratio < 1.4 and 100 < area < 6400):
                
                # Análisis de la región
                x1, y1, x2, y2 = bbox['x1'], bbox['y1'], bbox['x2'], bbox['y2']
                roi = gray[y1:y2, x1:x2]
                
                if roi.size > 0:
                    # Análisis de intensidad
                    mean_intensity = np.mean(roi)
                    std_intensity = np.std(roi)
                    
                    # Análisis de bordes en ROI
                    roi_edges = cv2.Canny(roi, 30, 100)
                    edge_density = np.sum(roi_edges > 0) / roi.size
                    
                    checkbox_score = (
                        detection['confidence'] * 0.4 +
                        (1 - abs(aspect_ratio - 1)) * 0.3 +
                        edge_density * 0.3
                    )
                    
                    checkbox_candidates.append({
                        **detection,
                        'type': 'checkbox_candidate',
                        'analysis': {
                            'aspect_ratio': float(aspect_ratio),
                            'mean_intensity': float(mean_intensity),
                            'std_intensity': float(std_intensity),
                            'edge_density': float(edge_density),
                            'checkbox_score': float(checkbox_score)
                        }
                    })
        
        # Análisis morfológico directo
        for contour in contours:
            area = cv2.contourArea(contour)
            if 100 < area < 5000:
                # Aproximar contorno
                epsilon = 0.02 * cv2.arcLength(contour, True)
                approx = cv2.approxPolyDP(contour, epsilon, True)
                
                # Buscar formas rectangulares
                if len(approx) >= 4:
                    x, y, w, h = cv2.boundingRect(contour)
                    aspect_ratio = w / h if h > 0 else 0
                    extent = area / (w * h) if w * h > 0 else 0
                    
                    if (0.7 < aspect_ratio < 1.3 and extent > 0.6):
                        # Analizar contenido
                        roi = gray[y:y+h, x:x+w]
                        mean_val = np.mean(roi)
                        
                        # Detectar si está marcado
                        is_filled = mean_val < 100  # Umbral para detectar marca
                        
                        morphological_candidates.append({
                            'bbox': {
                                'x1': int(x), 'y1': int(y),
                                'x2': int(x+w), 'y2': int(y+h),
                                'width': int(w), 'height': int(h),
                                'area': int(area)
                            },
                            'type': 'morphological_checkbox',
                            'analysis': {
                                'aspect_ratio': float(aspect_ratio),
                                'extent': float(extent),
                                'mean_intensity': float(mean_val),
                                'is_filled': bool(is_filled),
                                'vertices': len(approx)
                            }
                        })
        
        return {
            "model": self.model_name,
            "yolo_candidates": checkbox_candidates,
            "morphological_candidates": morphological_candidates,
            "total_yolo": len(checkbox_candidates),
            "total_morphological": len(morphological_candidates),
            "combined_analysis": self._combine_checkbox_analysis(checkbox_candidates, morphological_candidates)
        }
    
    def _combine_checkbox_analysis(self, yolo_candidates, morph_candidates):
        """
        Combinar análisis YOLO y morfológico para mejor detección
        """
        combined = []
        threshold_distance = 30  # Píxeles de tolerancia
        
        for yolo_cb in yolo_candidates:
            yolo_center = (
                yolo_cb['bbox']['center_x'],
                yolo_cb['bbox']['center_y']
            )
            
            best_match = None
            min_distance = float('inf')
            
            for morph_cb in morph_candidates:
                morph_center = (
                    (morph_cb['bbox']['x1'] + morph_cb['bbox']['x2']) // 2,
                    (morph_cb['bbox']['y1'] + morph_cb['bbox']['y2']) // 2
                )
                
                distance = np.sqrt(
                    (yolo_center[0] - morph_center[0])**2 +
                    (yolo_center[1] - morph_center[1])**2
                )
                
                if distance < min_distance and distance < threshold_distance:
                    min_distance = distance
                    best_match = morph_cb
            
            if best_match:
                # Combinar información
                combined_score = (
                    yolo_cb['analysis']['checkbox_score'] * 0.6 +
                    best_match['analysis']['extent'] * 0.4
                )
                
                combined.append({
                    'bbox': yolo_cb['bbox'],
                    'confidence': yolo_cb['confidence'],
                    'type': 'validated_checkbox',
                    'yolo_analysis': yolo_cb['analysis'],
                    'morphological_analysis': best_match['analysis'],
                    'combined_score': float(combined_score),
                    'match_distance': float(min_distance)
                })
        
        return sorted(combined, key=lambda x: x['combined_score'], reverse=True)
    
    def draw_detections(self, image, detections_result):
        """
        Dibujar detecciones con información detallada
        """
        output = image.copy()
        
        for detection in detections_result.get("detections", []):
            bbox = detection['bbox']
            x1, y1, x2, y2 = bbox['x1'], bbox['y1'], bbox['x2'], bbox['y2']
            
            # Color según confianza
            confidence = detection['confidence']
            if confidence > 0.8:
                color = (0, 255, 0)  # Verde alto
            elif confidence > 0.6:
                color = (0, 255, 255)  # Amarillo medio
            else:
                color = (0, 165, 255)  # Naranja bajo
            
            # Grosor según área
            area_pct = detection['metrics']['area_percentage']
            thickness = max(1, min(4, int(area_pct / 2)))
            
            # Dibujar rectángulo
            cv2.rectangle(output, (x1, y1), (x2, y2), color, thickness)
            
            # Información detallada
            class_name = detection['class_name']
            conf = detection['confidence']
            area = bbox['area']
            aspect_ratio = detection['metrics']['aspect_ratio']
            
            # Etiquetas múltiples
            labels = [
                f"{class_name}: {conf:.2f}",
                f"Area: {area}px",
                f"AR: {aspect_ratio:.2f}"
            ]
            
            # Dibujar etiquetas
            for i, label in enumerate(labels):
                y_offset = y1 - 10 - (i * 15)
                if y_offset < 15:
                    y_offset = y2 + 15 + (i * 15)
                
                cv2.putText(output, label, (x1, y_offset),
                           cv2.FONT_HERSHEY_SIMPLEX, 0.4, color, 1)
            
            # Punto central
            center_x, center_y = bbox['center_x'], bbox['center_y']
            cv2.circle(output, (center_x, center_y), 3, color, -1)
        
        # Estadísticas en la imagen
        stats = detections_result.get("statistics", {})
        if stats:
            info_text = [
                f"Objects: {stats.get('total_objects', 0)}",
                f"Coverage: {stats.get('coverage_percentage', 0):.1f}%",
                f"Density: {stats.get('density_score', 0):.2f}"
            ]
            
            for i, text in enumerate(info_text):
                cv2.putText(output, text, (10, 25 + i * 20),
                           cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 255, 255), 2)
        
        return output
    
    def analyze_spatial_relationships(self, detections_result):
        """
        Analizar relaciones espaciales entre objetos detectados
        """
        detections = detections_result.get("detections", [])
        if len(detections) < 2:
            return {"relationships": [], "clusters": []}
        
        relationships = []
        
        for i, det1 in enumerate(detections):
            for j, det2 in enumerate(detections[i+1:], i+1):
                # Calcular distancia
                pos1 = det1['metrics']['relative_position']
                pos2 = det2['metrics']['relative_position']
                
                distance = np.sqrt(
                    (pos1['x'] - pos2['x'])**2 + (pos1['y'] - pos2['y'])**2
                )
                
                # Calcular solapamiento
                bbox1 = det1['bbox']
                bbox2 = det2['bbox']
                
                overlap_x = max(0, min(bbox1['x2'], bbox2['x2']) - max(bbox1['x1'], bbox2['x1']))
                overlap_y = max(0, min(bbox1['y2'], bbox2['y2']) - max(bbox1['y1'], bbox2['y1']))
                overlap_area = overlap_x * overlap_y
                
                union_area = bbox1['area'] + bbox2['area'] - overlap_area
                iou = overlap_area / union_area if union_area > 0 else 0
                
                # Relación direccional
                dx = pos2['x'] - pos1['x']
                dy = pos2['y'] - pos1['y']
                
                if abs(dx) > abs(dy):
                    direction = "right" if dx > 0 else "left"
                else:
                    direction = "below" if dy > 0 else "above"
                
                relationships.append({
                    'object1': {'id': i, 'class': det1['class_name']},
                    'object2': {'id': j, 'class': det2['class_name']},
                    'distance': float(distance),
                    'iou': float(iou),
                    'direction': direction,
                    'relative_size': float(bbox1['area'] / bbox2['area'])
                })
        
        # Clustering simple por proximidad
        clusters = self._cluster_detections(detections)
        
        return {
            "relationships": sorted(relationships, key=lambda x: x['distance']),
            "clusters": clusters,
            "total_relationships": len(relationships)
        }
    
    def _cluster_detections(self, detections, distance_threshold=0.2):
        """
        Agrupar detecciones por proximidad espacial
        """
        if not detections:
            return []
        
        clusters = []
        visited = set()
        
        for i, detection in enumerate(detections):
            if i in visited:
                continue
            
            cluster = [i]
            visited.add(i)
            pos1 = detection['metrics']['relative_position']
            
            for j, other_detection in enumerate(detections):
                if j in visited:
                    continue
                
                pos2 = other_detection['metrics']['relative_position']
                distance = np.sqrt(
                    (pos1['x'] - pos2['x'])**2 + (pos1['y'] - pos2['y'])**2
                )
                
                if distance < distance_threshold:
                    cluster.append(j)
                    visited.add(j)
            
            if len(cluster) > 1:
                cluster_info = {
                    'members': cluster,
                    'size': len(cluster),
                    'classes': [detections[idx]['class_name'] for idx in cluster],
                    'center': self._calculate_cluster_center([detections[idx] for idx in cluster]),
                    'total_area': sum(detections[idx]['bbox']['area'] for idx in cluster)
                }
                clusters.append(cluster_info)
        
        return sorted(clusters, key=lambda x: x['size'], reverse=True)
    
    def _calculate_cluster_center(self, cluster_detections):
        """
        Calcular centro de un cluster de detecciones
        """
        positions = [d['metrics']['relative_position'] for d in cluster_detections]
        avg_x = np.mean([p['x'] for p in positions])
        avg_y = np.mean([p['y'] for p in positions])
        
        return {'x': float(avg_x), 'y': float(avg_y)}
    
    def batch_analysis(self, images, analysis_types=['objects', 'checkboxes']):
        """
        Análisis en lote de múltiples imágenes
        """
        results = []
        
        for i, image in enumerate(images):
            image_result = {
                'image_index': i,
                'results': {},
                'processing_time': 0
            }
            
            start_time = time.time()
            
            try:
                if 'objects' in analysis_types:
                    obj_result = self.detect_objects(image)
                    image_result['results']['objects'] = obj_result
                    
                    if 'relationships' in analysis_types:
                        rel_result = self.analyze_spatial_relationships(obj_result)
                        image_result['results']['relationships'] = rel_result
                
                if 'checkboxes' in analysis_types:
                    cb_result = self.detect_checkboxes(image)
                    image_result['results']['checkboxes'] = cb_result
                
                image_result['success'] = True
                
            except Exception as e:
                image_result['success'] = False
                image_result['error'] = str(e)
            
            image_result['processing_time'] = time.time() - start_time
            results.append(image_result)
        
        # Estadísticas del lote
        batch_stats = self._calculate_batch_statistics(results)
        
        return {
            'results': results,
            'batch_statistics': batch_stats,
            'total_images': len(images),
            'successful': len([r for r in results if r['success']]),
            'failed': len([r for r in results if not r['success']])
        }
    
    def _calculate_batch_statistics(self, batch_results):
        """
        Calcular estadísticas agregadas del lote
        """
        successful_results = [r for r in batch_results if r['success']]
        
        if not successful_results:
            return {}
        
        # Agregaciones
        total_objects = sum(
            r['results'].get('objects', {}).get('total', 0) 
            for r in successful_results
        )
        
        avg_processing_time = np.mean([r['processing_time'] for r in successful_results])
        
        # Distribución de clases agregada
        class_counts = {}
        for result in successful_results:
            obj_results = result['results'].get('objects', {})
            for detection in obj_results.get('detections', []):
                class_name = detection['class_name']
                class_counts[class_name] = class_counts.get(class_name, 0) + 1
        
        # Métricas de confianza agregadas
        all_confidences = []
        for result in successful_results:
            obj_results = result['results'].get('objects', {})
            all_confidences.extend([
                d['confidence'] for d in obj_results.get('detections', [])
            ])
        
        confidence_stats = {}
        if all_confidences:
            confidence_stats = {
                'mean': float(np.mean(all_confidences)),
                'std': float(np.std(all_confidences)),
                'min': float(np.min(all_confidences)),
                'max': float(np.max(all_confidences))
            }
        
        return {
            'total_objects_all_images': total_objects,
            'avg_objects_per_image': total_objects / len(successful_results),
            'avg_processing_time': float(avg_processing_time),
            'class_distribution': class_counts,
            'confidence_statistics': confidence_stats,
            'images_processed': len(successful_results)
        }
    
    def performance_benchmark(self, test_image, iterations=10):
        """
        Benchmark de rendimiento del modelo
        """
        import time
        
        if self.model is None:
            return {"error": "Modelo YOLO no disponible"}
        
        times = []
        
        for i in range(iterations):
            start_time = time.time()
            
            try:
                result = self.detect_objects(test_image, confidence_threshold=0.5)
                
                end_time = time.time()
                times.append(end_time - start_time)
                
            except Exception as e:
                return {"error": f"Error en benchmark: {str(e)}"}
        
        return {
            'model': self.model_name,
            'iterations': iterations,
            'timing': {
                'mean': float(np.mean(times)),
                'std': float(np.std(times)),
                'min': float(np.min(times)),
                'max': float(np.max(times)),
                'fps_avg': float(1.0 / np.mean(times))
            },
            'hardware': {
                'device': 'cpu',
                'acceleration': 'none'
            }
        }

# Instancia global del servicio YOLO
yolo_service = YOLOService()