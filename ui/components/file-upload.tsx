"use client";

import { useState, useRef, useEffect } from "react";
import { PlusIcon, FilePlus2Icon } from "lucide-react";

type FileUploadProps = {
    onFileSelect: (files: File[]) => void;
    disabled?: boolean;
};

export function FileUpload({ onFileSelect, disabled = false }: FileUploadProps) {
    const [showMenu, setShowMenu] = useState(false);
    const [showTooltip, setShowTooltip] = useState(false);
    const fileInputRef = useRef<HTMLInputElement>(null);
    const menuRef = useRef<HTMLDivElement>(null);
    const buttonRef = useRef<HTMLButtonElement>(null);

    const handleButtonClick = () => {
        if (disabled) return;
        setShowMenu(!showMenu);
    };

    const handleUploadClick = () => {
        if (fileInputRef.current) {
            fileInputRef.current.click();
        }
        setShowMenu(false);
    };

    const handleFileChange = (e: React.ChangeEvent<HTMLInputElement>) => {
        if (e.target.files && e.target.files.length > 0) {
            const filesArray = Array.from(e.target.files);
            onFileSelect(filesArray);
        }
    };

    // Handle clicks outside the menu
    useEffect(() => {
        const handleClickOutside = (event: MouseEvent) => {
            if (showMenu &&
                menuRef.current &&
                buttonRef.current &&
                !menuRef.current.contains(event.target as Node) &&
                !buttonRef.current.contains(event.target as Node)) {
                setShowMenu(false);
            }
        };

        document.addEventListener('mousedown', handleClickOutside);
        return () => {
            document.removeEventListener('mousedown', handleClickOutside);
        };
    }, [showMenu]);

    return (
        <div className="relative">
            {/* Tooltip */}
            {showTooltip && !showMenu && (
                <div className="absolute bottom-full left-1/2 transform -translate-x-1/2 mb-2 px-3 py-2 bg-white text-[#343541] text-xs rounded whitespace-nowrap shadow-md">
                    Upload Files
                    <div className="absolute top-full left-1/2 transform -translate-x-1/2 border-4 border-transparent border-t-white"></div>
                </div>
            )}

            {/* Upload Button (Round) */}
            <button
                ref={buttonRef}
                type="button"
                onClick={handleButtonClick}
                disabled={disabled}
                onMouseEnter={() => setShowTooltip(true)}
                onMouseLeave={() => setShowTooltip(false)}
                className={`rounded-full h-10 w-10 flex items-center justify-center 
                    bg-[#565869] text-white hover:bg-[#676980]
                    ${disabled ? 'opacity-40 cursor-not-allowed' : 'cursor-pointer'}
                    transition-colors`}
                title="Upload Files"
            >
                <PlusIcon className="h-5 w-5" />
            </button>

            {/* Dropdown Menu with Rounded Container and Option */}
            {showMenu && (
                <div
                    ref={menuRef}
                    className="absolute bottom-full left-0 mb-2 bg-[#40414f] rounded-xl shadow-lg overflow-hidden z-10 whitespace-nowrap"
                >
                    <div className="py-1">
                        <div
                            className="px-4 py-3 mx-2 my-1 text-white bg-[#4a4b59] hover:bg-[#565869] cursor-pointer rounded-lg flex items-center gap-2"
                            onClick={handleUploadClick}
                        >
                            <FilePlus2Icon className="h-5 w-5" />
                            <span>Upload from computer</span>
                        </div>
                    </div>
                    <input
                        type="file"
                        ref={fileInputRef}
                        onChange={handleFileChange}
                        multiple
                        className="hidden"
                    />
                </div>
            )}
        </div>
    );
} 